import asyncio
import contextlib
import json
import logging
from typing import Any, Optional

import aiohttp
from blinker import signal

from lmk.utils.blinker import wait_for_signal
from lmk.utils.asyncio import async_retry, RetryRule


LOGGER = logging.getLogger(__name__)


ws_connected = signal("ws-connected")

ws_disconnected = signal("ws-disconnected")

ws_closed = signal("ws-closed")


class WebSocket:
    """
    Wrapper for aiohttp's web socket interface that supports retries
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        retry_rule: Optional[RetryRule] = None,
        **kwargs,
    ) -> None:
        self.session = session
        self.url = url
        self.kwargs = kwargs
        self.retry_rule = retry_rule

        self.queue = asyncio.Queue()
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.ws_ctx = None
        self.send_task: Optional[asyncio.Task] = None
        self.close_event = asyncio.Event()

    def _check_state(self, initialized: bool) -> None:
        if self.ws is None and initialized:
            raise RuntimeError("Context not initialized")
        if self.ws is not None and not initialized:
            raise RuntimeError("Context not initialized")

    async def close(self) -> None:
        self.close_event.set()
        if self.send_task is not None:
            await self.send_task
        if self.ws is not None:
            await self.ws.close()

    async def _setup(self) -> None:
        self._check_state(False)

        @async_retry(rule=self.retry_rule)
        async def init():
            try:
                self.ws_ctx = self.session.ws_connect(self.url, **self.kwargs)
                self.ws = await self.ws_ctx.__aenter__()
                LOGGER.debug("Initialized web socket")
            except:
                LOGGER.exception("Web socket error")
                self.ws_ctx = None
                self.ws = None
                raise
            else:
                ws_connected.send(self)

        await init()

    async def _teardown(self) -> None:
        if self.ws_ctx is None:
            return
        await self.ws_ctx.__aexit__(None, None, None)
        self.ws_ctx = None
        self.ws = None
        ws_disconnected.send(self)

    async def __aenter__(self):
        self.send_task = asyncio.create_task(self._sender())
        await self._setup()
        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        await self.queue.join()

        self.send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.send_task

        await self._teardown()
        ws_closed.send(self)

    async def send(self, data: Any) -> None:
        """ """
        future = asyncio.Future()
        await self.queue.put((data, future))
        await future

    async def _iterate(self):
        self._check_state(True)

        close_message: Optional[aiohttp.WSMessage] = None
        while True:
            message = await self.ws.receive()
            LOGGER.debug("Received message %s", message)
            if message.type == aiohttp.WSMsgType.CLOSED:
                if close_message is None and not self.close_event.is_set():
                    raise WSDisconnected
                break
            if message.type == aiohttp.WSMsgType.CLOSE:
                close_message = message
                continue
            if message.type == aiohttp.WSMsgType.ERROR:
                raise WSConnectionError(message.data)
            if message.type == aiohttp.WSMsgType.TEXT:
                try:
                    decoded = json.loads(message.data)
                except json.JSONDecodeError as err:
                    raise InvalidWSMessage(message.data) from err
                yield decoded
                continue
            if message.type == aiohttp.WSMsgType.CLOSING:
                continue

            LOGGER.warn("Unhandled websocket message type: %s", message)

        if close_message is not None and close_message.data != aiohttp.WSCloseCode.OK:
            raise WSCloseError(close_message.data, close_message.extra)

    async def _iterate_with_retry(self):
        while True:
            try:
                async for item in self._iterate():
                    yield item
                break
            except (WSDisconnected, WSCloseError, WSConnectionError) as error:
                LOGGER.error("WS Disconnected. Reconnecting (%r)", error)
                await self._teardown()
                await self._setup()
            except GeneratorExit:
                break
            except asyncio.exceptions.CancelledError:
                raise
            except:
                LOGGER.exception("Unexpected error in websocket")
                raise

    async def _sender(self):
        buffer = []

        if self.ws is None:
            connect_task = wait_for_signal(ws_connected, self)
        else:
            connect_task = asyncio.Future()
            connect_task.set_result(None)

        async def queue_get():
            try:
                return await self.queue.get()
            except RuntimeError as error:
                if str(error) == "Event loop is closed":
                    return None
                raise

        queue_task = asyncio.create_task(queue_get())

        close_task = asyncio.create_task(self.close_event.wait())

        while True:
            LOGGER.debug("Before loop")
            await asyncio.wait(
                [connect_task, queue_task, close_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            LOGGER.debug(
                "Loop; connected: %s, queue: %s", connect_task.done(), queue_task.done()
            )

            if queue_task.done():
                result = queue_task.result()
                if result is not None:
                    buffer.append(queue_task.result())
                queue_task = asyncio.create_task(queue_get())

            while buffer and self.ws is not None:
                item, future = buffer.pop(0)
                await self.ws.send_json(item)
                future.set_result(None)
                self.queue.task_done()

            if connect_task.done():
                connect_task = wait_for_signal(ws_connected, self)

            if close_task.done():
                break

    async def __aiter__(self):
        """ """
        self._check_state(True)

        async for item in self._iterate_with_retry():
            yield item
            if self.send_task.done():
                self.send_task.result()


class WSError(Exception):
    """ """


class WSDisconnected(WSError):
    """ """

    def __init__(self) -> None:
        super().__init__(f"Web socket disconnected uncleanly")


class WSConnectionError(WSError):
    """ """

    def __init__(self, data: str) -> None:
        super().__init__(f"Web socket error: {data}")


class InvalidWSMessage(WSError):
    """ """

    def __init__(self, data: str) -> None:
        super().__init__(f"Invalid WS message: {data}")


class WSCloseError(WSError):
    """ """

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(
            f"Web socket closed unexpectedly. Code: {code}, " f"reason: {reason}"
        )
