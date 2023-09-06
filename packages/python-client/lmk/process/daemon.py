import asyncio
import contextlib
import json
import logging
import multiprocessing
import os
import signal
import socket
import textwrap
from functools import wraps
from typing import Optional, Callable, Any, cast, Awaitable, AsyncGenerator

from aiohttp import web

from lmk.generated.models.event_response import EventResponse
from lmk.generated.models.session_response import SessionResponse
from lmk.generated.models.process_session_state import ProcessSessionState
from lmk.instance import get_instance
from lmk.process import exc
from lmk.process.manager import JobManager
from lmk.process.models import Job
from lmk.process.monitor import ProcessMonitor, MonitoredProcess
from lmk.utils import (
    setup_logging,
    socket_exists,
    read_last_lines,
    shlex_join,
    asyncio_event,
)
from lmk.utils.ws import WebSocket


LOGGER = logging.getLogger(__name__)


def route_handler(func: Callable) -> Callable:
    """ """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            LOGGER.exception("Error running route handler")
            return web.json_response({"message": "Internal server error"}, status=500)

    return wrapper


@contextlib.contextmanager
def pid_ctx(pid_file: str, pid: int):
    with open(pid_file, "w+") as f:
        f.write(str(pid))
    try:
        yield
    finally:
        if os.path.exists(pid_file):
            os.remove(pid_file)


class ProcessMonitorController:
    """ """

    def __init__(
        self,
        job_name: str,
        monitor: ProcessMonitor,
        manager: JobManager,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.job_name = job_name
        self.manager = manager
        self.monitor = monitor
        self.hostname = socket.gethostname()

        self.done_event = asyncio_event(loop=loop)
        self.attached_event = asyncio_event(loop=loop)
        self.update_event = asyncio_event(loop=loop)
        self.session: Optional[SessionResponse] = None
        self.process: Optional[MonitoredProcess] = None

    def _should_notify(self, job: Job) -> bool:
        if job.notify_on == "error":
            return job.exit_code != 0
        if job.notify_on == "stop":
            return True
        return False

    @route_handler
    async def _wait_websocket(self, request: web.Request) -> web.WebSocketResponse:
        wait_for = request.query.get("wait_for") or "run"
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        attached_set = self.attached_event.is_set()
        if not attached_set:
            await self.attached_event.wait()

            job = await self.manager.get_job(self.job_name)
            if job is None:
                raise exc.JobNotFound(self.job_name)

            if job.error is not None:
                await ws.send_json(
                    {
                        "ok": False,
                        "stage": "attach",
                        "error_type": job.error_type,
                        "error": job.error,
                    }
                )
                await ws.close()
                return ws

        if wait_for == "attach":
            await ws.send_json({"ok": True, "stage": "attach"})
            await ws.close()
            return ws

        await self.done_event.wait()
        job = await self.manager.get_job(self.job_name)

        if job is None:
            raise exc.JobNotFound(self.job_name)

        if job.error is not None:
            await ws.send_json(
                {
                    "ok": False,
                    "stage": "run",
                    "error_type": job.error_type,
                    "error": job.error,
                }
            )
            await ws.close()
            return ws

        await ws.send_json({"ok": True, "stage": "run", "exit_code": job.exit_code})
        await ws.close()
        return ws

    @route_handler
    async def _handle_update(self, request: web.Request) -> web.Response:
        self.update_event.set()

        return web.json_response({"ok": True})

    @route_handler
    async def _send_signal(self, request: web.Request) -> web.Response:
        body = await request.json()
        signum = body["signal"]
        if isinstance(signum, str):
            signum = getattr(signal.Signals, signum).value

        await self.send_signal(signum)

        return web.json_response({"ok": True})

    async def _handle_session_action(self, action: str, body: Optional[Any]) -> None:
        if action == "sendSignal" and body is not None:
            await self.send_signal(body["signal"])
            return
        LOGGER.error("Invalid session action: %s, body: %s", action, body)

    @contextlib.asynccontextmanager
    async def _session_ctx(self) -> AsyncGenerator[None, None]:
        instance = get_instance()
        job = await self.manager.get_job(self.job_name)
        if job is None:
            raise exc.JobNotFound(self.job_name)

        self.session = await cast(
            Awaitable[SessionResponse],
            instance.create_session(
                self.job_name,
                ProcessSessionState(
                    type="process",
                    hostname=self.hostname,
                    command=shlex_join(json.loads(job.command))
                    if job.command
                    else "<unknown>",
                    pid=cast(float, job.pid),
                    notifyOn=job.notify_on,
                    notifyChannel=job.channel_id,
                    exitCode=None,
                ),
                async_req=True,
            ),
        )

        LOGGER.info("Created session: %s", self.session.session_id)
        await self.manager.update_job(self.job_name, session_id=self.session.session_id)

        ws: WebSocket
        async with instance.session_connect(self.session.session_id, False) as ws:
            LOGGER.debug("Connected to session: %s", self.session.session_id)

            async def handle_updates():
                while True:
                    update_task = asyncio.create_task(self.update_event.wait())
                    done_task = asyncio.create_task(self.done_event.wait())
                    await asyncio.wait(
                        [update_task, done_task], return_when=asyncio.FIRST_COMPLETED
                    )

                    job = await self.manager.get_job(self.job_name)

                    if update_task.done():
                        self.update_event.clear()
                        await ws.send(
                            {
                                "notifyOn": job.notify_on,
                                "notifyChannel": job.channel_id,
                            }
                        )

                    if done_task.done():
                        LOGGER.info(
                            "Sending session exit message; exit code %s", job.exit_code
                        )
                        await ws.send(
                            {
                                "notifyOn": job.notify_on,
                                "notifyChannel": job.channel_id,
                                "exitCode": job.exit_code,
                            }
                        )
                        LOGGER.info("Sent message")
                        await ws.close()
                        break

            async def handle_messages():
                async for message in ws:
                    LOGGER.debug("Web socket message: %s", message)
                    if not message["ok"]:
                        LOGGER.error("Error in websocket: %s", message)
                        continue
                    msg_type = message["message"]["type"]
                    if msg_type == "update":
                        await self.manager.update_job(
                            self.job_name,
                            notify_on=message["message"]["session"]["state"][
                                "notifyOn"
                            ],
                            channel_id=message["message"]["session"]["state"].get(
                                "notifyChannel"
                            ),
                        )
                    elif msg_type == "action":
                        try:
                            action = message["message"]["action"]
                            body = message["message"].get("body")
                            await self._handle_session_action(action, body)
                        except Exception as err:
                            LOGGER.exception(
                                "Error running action for message: %s", message
                            )
                    else:
                        LOGGER.warn("Unhandled ws message type: %s", msg_type)

            updates_task = asyncio.create_task(handle_updates())
            messages_task = asyncio.create_task(handle_messages())
            try:
                yield
            finally:
                LOGGER.debug("Waiting for session tasks")
                await asyncio.gather(updates_task, messages_task)
                LOGGER.debug("Session tasks are done")
                if self.session is not None:
                    await cast(
                        Awaitable[None],
                        instance.end_session(self.session.session_id, async_req=True),
                    )

    async def _run_server(self) -> None:
        socket_path = self.manager.socket_file(self.job_name)

        app = web.Application()

        app.add_routes(
            [
                web.get("/wait", self._wait_websocket),
                web.post("/signal", self._send_signal),
                web.post("/update", self._handle_update),
            ]
        )

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.UnixSite(runner, socket_path)
        await site.start()

        while True:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                await runner.cleanup()
                if socket_exists(socket_path):
                    os.remove(socket_path)
                raise

    async def _run_command(self, log_path: str, log_level: str) -> None:
        async with contextlib.AsyncExitStack() as stack:
            output_path = self.manager.output_file(self.job_name)
            job = await self.manager.get_job(self.job_name)

            try:
                if job is None:
                    raise exc.JobNotFound(self.job_name)

                # Create the output file
                with open(output_path, "wb+") as f:
                    pass

                LOGGER.debug("Attaching to process")
                self.process = await self.monitor.attach(
                    output_path,
                    log_path,
                    log_level,
                )
                LOGGER.debug(
                    "Attached to %d (%s)", self.process.pid, self.process.command
                )
                await self.manager.update_job(
                    self.job_name,
                    pid=self.process.pid,
                    command=self.process.command,
                )
                self.attached_event.set()

                await stack.enter_async_context(self._session_ctx())

                LOGGER.debug(
                    "Entered session context: %s",
                    self.session.session_id if self.session else "<unknown>",
                )

                exit_code = await self.process.wait()
                job = await self.manager.end_job(
                    self.job_name,
                    exit_code=exit_code,
                )
            except Exception as err:
                job = await self.manager.end_job(self.job_name, exit_code=-1, error=err)
                if not self.attached_event.is_set():
                    self.attached_event.set()

                LOGGER.exception(
                    "%d: %s monitor raised exception",
                    job.pid,
                    type(self.monitor).__name__,
                )
            else:
                LOGGER.info("%d: exited with code %d", job.pid, job.exit_code)
            finally:
                should_notify = self._should_notify(cast(Job, job))

            self.done_event.set()

            notify_status = "none"
            if not should_notify:
                LOGGER.info(
                    "Not sending notification. Current notify on: %s", job.notify_on
                )
            else:
                LOGGER.info(
                    "Sending notification to channel %s. Current notify on: %s",
                    job.channel_id or "default",
                    job.notify_on,
                )
                instance = get_instance()
                try:
                    message = textwrap.dedent(
                        f"""
                        Process exited with code **{exit_code}**:
                        ```bash
                        {shlex_join(json.loads(job.command)) if job.command else "<unknown>"}
                        ```
                        Process ran on `{self.hostname}`

                        Started: {job.started_at.isoformat() if job.started_at else "<unknown>"}
                        
                        Ended: {job.ended_at.isoformat() if job.ended_at else "<unknown>"}
                        """
                    ).strip()

                    logs = "\n".join(read_last_lines(output_path, 10, 10000))

                    if logs:
                        message += f"\n\nMost recent logs:\n```\n{logs}\n```"

                    await cast(
                        Awaitable[EventResponse],
                        instance.notify(
                            message,
                            notification_channels=(
                                None if job.channel_id is None else [job.channel_id]
                            ),
                            async_req=True,
                        ),
                    )
                    notify_status = "success"
                except Exception:
                    LOGGER.exception(
                        "Failed to send notification to channel %s.", job.channel_id
                    )
                    notify_status = "failed"

            await self.manager.update_job(self.job_name, notify_status=notify_status)

    async def send_signal(self, signum: int) -> None:
        if self.process is None:
            raise exc.ProcessNotAttached
        await self.process.send_signal(signum)

    async def run(self, log_path: str, log_level: str) -> None:
        await self.manager.start_job(self.job_name)

        tasks = []
        tasks.append(asyncio.create_task(self._run_server()))

        LOGGER.info("Running main process")
        try:
            await self._run_command(log_path, log_level)
        except Exception:
            LOGGER.exception("Error running command")
            raise
        finally:
            for task in reversed(tasks):
                task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait(tasks)


class ProcessMonitorDaemon(multiprocessing.Process):
    """ """

    def __init__(
        self,
        job_name: str,
        monitor: ProcessMonitor,
        base_path: Optional[str] = None,
        log_level: str = "INFO",
    ) -> None:
        super().__init__(daemon=False)
        self.job_name = job_name
        self.monitor = monitor
        self.base_path = base_path
        self.log_level = log_level

    def run(self) -> None:
        # Double fork so the process continues to run
        if os.fork() != 0:
            return

        # Detach this process from the parent so we don't share
        # signals
        os.setsid()

        manager = JobManager(self.base_path)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        controller = ProcessMonitorController(
            self.job_name, self.monitor, manager, loop=loop
        )

        try:
            log_path = manager.log_file(self.job_name)
            pid_file = manager.pid_file(self.job_name)
            with open(log_path, "a+") as log_stream:
                setup_logging(log_stream=log_stream, level=self.log_level)

                with pid_ctx(pid_file, cast(int, self.pid)):
                    try:
                        loop.run_until_complete(
                            controller.run(log_path, self.log_level)
                        )
                    finally:
                        loop.run_until_complete(loop.shutdown_asyncgens())
                        loop.close()
        except:
            LOGGER.exception("Error running process monitor daemon")
            raise
