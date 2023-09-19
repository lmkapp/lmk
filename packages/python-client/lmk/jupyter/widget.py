import asyncio
import atexit
import contextlib
import enum
import logging
import io
import os
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Union, Optional, cast

from ipywidgets import DOMWidget
from traitlets import Unicode, Int, List, Dict, UseEnum

from lmk import exc
from lmk.generated.api.app_api import AppApi
from lmk.generated.models.jupyter_session_state import JupyterSessionState
from lmk.generated.models.session_response import SessionResponse
from lmk.generated.exceptions import ApiException
from lmk.instance import (
    Instance,
    default_instance_changed,
    default_channel_changed,
    access_token_changed,
    server_url_changed,
    channels_fetch_state_changed,
    get_instance,
    ChannelsState,
    Channels,
)
from lmk.jupyter.colab import observe_google_colab_url, colab_support_enabled
from lmk.jupyter.constants import MODULE_NAME, MODULE_VERSION
from lmk.jupyter.history import (
    IPythonHistory,
    jupyter_cell_state_changed,
    jupyter_state_changed,
    IPythonShellState,
)
from lmk.jupyter.notebook_info import (
    NotebookInfoWatcher,
    notebook_name_changed,
    kernel_id,
)
from lmk.jupyter.utils import background_ctx
from lmk.utils.asyncio import loop_ctx, asyncio_event, asyncio_lock, asyncio_queue
from lmk.utils.blinker import wait_for_signal
from lmk.utils.logging import setup_logging
from lmk.utils.ws import WebSocket


LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_PATH = os.path.expanduser("~/.lmk")


def truncate_stream(stream: io.StringIO, max_size: int) -> None:
    value = stream.getvalue()
    if len(value) <= max_size:
        return
    new_size = int(max_size * 0.8)
    stream.truncate(0)
    stream.seek(0)
    stream.write(value[-new_size:])


def ts_millis(dt: Optional[datetime] = None) -> int:
    if dt is None:
        dt = datetime.utcnow()
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def date_from_millis(ts: int) -> datetime:
    return datetime.utcfromtimestamp(ts / 1000.0).replace(tzinfo=timezone.utc)


def format_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%d %H:%M:%S")


class AuthState(str, enum.Enum):
    NeedsAuth = "needs-auth"
    AuthInProgress = "auth-in-progress"
    AuthError = "auth-error"
    Authenticated = "authenticated"


class IPythonCellStateType(str, enum.Enum):
    Running = "running"
    Error = "error"
    Success = "success"
    Cancelled = "cancelled"


class IPythonMonitoringState(str, enum.Enum):
    None_ = "none"
    Error = "error"
    Stop = "stop"


def default_log_path() -> str:
    kernel_uid = kernel_id() or str(uuid.uuid4())
    kernel_path = os.path.join(DEFAULT_BASE_PATH, "jupyter", kernel_uid)
    return os.path.join(kernel_path, "lmk.log")


class LMKWidget(DOMWidget):
    # Metadata needed for jupyter to find the widget
    _model_name = Unicode("LMKModel").tag(sync=True)
    _model_module = Unicode(MODULE_NAME).tag(sync=True)
    _model_module_version = Unicode(MODULE_VERSION).tag(sync=True)
    _view_name = Unicode("LMKView").tag(sync=True)
    _view_module = Unicode(MODULE_NAME).tag(sync=True)
    _view_module_version = Unicode(MODULE_VERSION).tag(sync=True)

    # Notebook metadata
    url = Unicode(None, allow_none=True).tag(sync=True)
    notebook_name = Unicode(None, allow_none=True).tag(sync=True)

    # Auth data
    auth_url = Unicode(None, allow_none=True).tag(sync=True)
    auth_state = UseEnum(AuthState, default_value=AuthState.NeedsAuth).tag(sync=True)
    auth_error = Unicode(None, allow_none=True).tag(sync=True)
    access_token = Unicode(None, allow_none=True).tag(sync=True)
    api_url = Unicode(None, allow_none=True).tag(sync=True)

    # Session data
    session = Dict(None, allow_none=True).tag(sync=True)

    # Jupyter state
    jupyter_state = UseEnum(
        IPythonShellState,
        default_value=None,
        allow_none=True,
    ).tag(sync=True)
    jupyter_execution_num = Int(None, allow_none=True).tag(sync=True)
    jupyter_cell_state = UseEnum(
        IPythonCellStateType, default_value=None, allow_none=True
    ).tag(sync=True)
    jupyter_cell_text = Unicode(None, allow_none=True).tag(sync=True)
    jupyter_cell_started_at = Int(None, allow_none=True).tag(sync=True)
    jupyter_cell_finished_at = Int(None, allow_none=True).tag(sync=True)
    jupyter_cell_error = Unicode(None, allow_none=True).tag(sync=True)

    # Current monitoring state--shared w/ BE
    monitoring_state = Unicode(IPythonMonitoringState.None_.value).tag(sync=True)

    # Params to tweak notification rules--getting notified about something really
    # short where you can obviously see the result would just be annoying
    notify_min_execution = Int(None, allow_none=True).tag(sync=True)
    notify_min_time = Int(None, allow_none=True).tag(sync=True)

    # Metadata about channels
    selected_channel = Unicode(None, allow_none=True).tag(sync=True)
    channels_state = UseEnum(ChannelsState, default_value=ChannelsState.None_).tag(
        sync=True
    )
    channels = List(Dict()).tag(sync=True)

    # Keep a log of sent notifications
    sent_notifications = List(Dict()).tag(sync=True)

    # Sync log level between component and here
    log_level = Unicode("ERROR")
    log_path = Unicode(default_log_path())

    def __init__(self) -> None:
        super().__init__()

        startup_event = threading.Event()

        self.thread = LMKWidgetThread(self, startup_event)
        self.thread.start()

        startup_event.wait(3)

    def set_monitoring_state(
        self,
        state: Union[IPythonMonitoringState, str],
        immediate: bool = False,
    ) -> None:
        if isinstance(state, str):
            state = IPythonMonitoringState(state)
        if state.value == self.monitoring_state:
            return
        self.monitoring_state = state.value
        min_time = ts_millis()
        min_execution = self.jupyter_execution_num
        if not immediate:
            min_time += 2000
            min_execution = (min_execution or 0) + 1

        self.notify_min_execution = min_execution
        self.notify_min_time = min_time

    def set_log_level(self, level: Union[int, str]) -> None:
        if isinstance(level, int):
            level = logging.getLevelName(level)
        self.log_level = cast(str, level)

    def shutdown(self) -> None:
        self.thread.shutdown()


class LMKWidgetThread(threading.Thread):
    """
    Background thread where all of the actual processing for the LMK
    jupyter widget happens
    """

    def __init__(self, widget: LMKWidget, startup_event: threading.Event) -> None:
        super().__init__()
        self.widget = widget
        self.startup_event = startup_event
        self.shutdown_event = threading.Event()
        self.history = IPythonHistory()
        self.info_watcher = NotebookInfoWatcher()
        self.loop = asyncio.new_event_loop()
        self._cancel_auth = asyncio_event(loop=self.loop)
        self._register_shutdown_hook()
        self._setup_logging()

    def _setup_logging(
        self, level: Optional[str] = None, file: Optional[str] = None
    ) -> None:
        if level is None:
            level = self.widget.log_level
        if file is None:
            file = self.widget.log_path

        file_dir = os.path.dirname(file)
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)
        setup_logging(disable_existing=False, level=level, log_file=file)

    def _register_shutdown_hook(self) -> None:
        atexit.register(self.shutdown)

    def shutdown(self) -> None:
        self.shutdown_event.set()
        self.join()

    async def handle_event(self, event):
        if event["name"] == "log_level":
            self._setup_logging(level=event["new"])
        elif event["name"] == "log_path":
            self._setup_logging(file=event["new"])
        elif event["name"] == "selected_channel":
            instance = get_instance()
            instance.default_channel = event["new"]

    async def initiate_auth(self, payload, instance: Instance):
        if self.widget.auth_state == AuthState.AuthInProgress:
            LOGGER.info(f"Skipping auth because it is in progress")
            return

        LOGGER.debug("Initiating auth")

        access_token = None
        try:
            access_token = await instance._get_access_token_async()
        except exc.NotLoggedIn:
            pass
        if access_token and not (payload or {}).get("force"):
            LOGGER.info("Using existing access token")
            self.widget.auth_state = AuthState.Authenticated
            return

        timeout = 300.0
        poll_interval = 1.0
        start = time.time()

        try:
            self.widget.auth_state = AuthState.AuthInProgress
            session = await instance.initiate_auth(async_req=True)  # type: ignore
            self.widget.auth_url = session.authorize_url

            cancellation_wait_task = asyncio.create_task(self._cancel_auth.wait())

            while time.time() - start < timeout and not self._cancel_auth.is_set():
                try:
                    response = await instance.retrieve_auth_token(  # type: ignore
                        session_id=session.session_id, async_req=True
                    )
                except exc.AuthSessionNotComplete:
                    await asyncio.wait(
                        [
                            asyncio.create_task(asyncio.sleep(poll_interval)),
                            cancellation_wait_task,
                        ],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    continue
                else:
                    instance.set_access_token(
                        response.access_token,
                        response.refresh_token,
                        datetime.utcnow() + timedelta(seconds=response.expires_in),
                    )
                    self.widget.auth_state = AuthState.Authenticated
                    self.widget.auth_url = None
                    self.widget.auth_error = None
                    return

            if self._cancel_auth.is_set():
                self._cancel_auth.clear()
                self.widget.auth_url = None
                self.widget.auth_state = (
                    AuthState.Authenticated
                    if instance.logged_in()
                    else AuthState.NeedsAuth
                )
                self.widget.auth_error = None
            else:
                self.widget.auth_state = AuthState.AuthError
                self.widget.auth_url = None
                self.widget.auth_error = "Authentication timed out"
        except Exception as err:
            self.widget.auth_state = AuthState.AuthError
            self.widget.auth_error = f"{type(err).__name__}: {err}"
            raise

    async def cancel_auth(self, payload, instance: Instance) -> None:
        self._cancel_auth.set()

    async def refresh_channels(self, payload, instance: Instance):
        if instance.channels.fetch_state != self.widget.channels_state:
            LOGGER.warn(
                "Widget channels fetch state is not synced properly "
                "with the Instance"
            )
            self.widget.channels_state = instance.channels.fetch_state

        if self.widget.channels_state == ChannelsState.Loading:
            LOGGER.info(f"Skipping channel fetch because it is in progress")
            return

        await instance.channels.fetch(async_req=True, force=True)  # type: ignore

    async def _handle_request_inner(self, request):
        method = request["method"]
        payload = request["payload"]
        instance = get_instance()
        if method == "initiate-auth":
            return await self.initiate_auth(payload, instance)
        if method == "cancel-auth":
            return await self.cancel_auth(payload, instance)
        if method == "refresh-channels":
            return await self.refresh_channels(payload, instance)
        raise ValueError(f"Invalid method {method}")

    async def handle_request(self, request):
        try:
            response = await self._handle_request_inner(request)
            return {
                "request_id": request["request_id"],
                "success": True,
                "payload": response,
            }
        except ApiException as err:
            LOGGER.error(
                "API Request failed with status %d %s: %s",
                err.status,
                err.reason,
                err.body,
            )
            return {
                "request_id": request["request_id"],
                "success": False,
                "error": str(err),
            }
        except Exception as err:
            LOGGER.exception("Error occurred when handling request")
            if not isinstance(request, dict):
                return {
                    "request_id": "<unknown>",
                    "success": False,
                    "error": "Invalid payload",
                }
            return {
                "request_id": request.get("request_id", "<unknown>"),
                "success": False,
                "error": str(err),
            }

    def _handle_done_future(self, future):
        try:
            future.result()
        except Exception:
            LOGGER.exception("Error in callback")

    def _observe_widget(self, loop: asyncio.AbstractEventLoop) -> Callable[[], None]:
        def observe(info):
            LOGGER.debug(
                "Change of `%s` from %r to %r",
                info["name"],
                info["old"],
                info["new"],
            )

            async def handle():
                with background_ctx(LOGGER, type(self).__name__):
                    await self.handle_event(info)

            task = loop.create_task(handle())
            task.add_done_callback(self._handle_done_future)

        self.widget.observe(observe)

        def observe_msg(widget, content, buffers):
            LOGGER.debug("Msg: %s", content)

            async def handle():
                with background_ctx(LOGGER, type(self).__name__):
                    response = await self.handle_request(content)
                    self.widget.send(response)

            task = loop.create_task(handle())
            task.add_done_callback(self._handle_done_future)

        self.widget.on_msg(observe_msg)

        def unobserve():
            self.widget.unobserve(observe)
            self.widget.on_msg(observe_msg, remove=True)

        return unobserve

    async def _send_notification(self) -> None:
        with background_ctx(LOGGER, type(self).__name__):
            instance = get_instance()

            kws = {}
            if self.widget.selected_channel is not None:
                kws["notification_channels"] = [self.widget.selected_channel]

            started = "<unknown>"
            if self.widget.jupyter_cell_started_at is not None:
                started = format_date(date_from_millis(self.widget.jupyter_cell_started_at))

            ended = "<unknown>"
            if self.widget.jupyter_cell_finished_at is not None:
                ended = format_date(date_from_millis(self.widget.jupyter_cell_finished_at))

            if self.widget.jupyter_cell_state == IPythonCellStateType.Error:
                message = (
                    f"Notebook [**{self.widget.notebook_name}**]({self.widget.url}) "
                    f"**failed** during execution **\\[{self.widget.jupyter_execution_num}\\]**:\n"
                    f"```python\n{self.widget.jupyter_cell_text}\n```\n\n"
                    f"Error:\n```\n{self.widget.jupyter_cell_error}\n```\n\n"
                    f"Started: {started}\n\n"
                    f"Ended: {ended}"
                )
            elif self.widget.jupyter_cell_state == IPythonCellStateType.Cancelled:
                message = (
                    f"Notebook [**{self.widget.notebook_name}**]({self.widget.url}) "
                    f"was **cancelled** during execution **\\[{self.widget.jupyter_execution_num}\\]**:\n"
                    f"```python\n{self.widget.jupyter_cell_text}\n```\n\n"
                    f"Started: {started}\n\n"
                    f"Ended: {ended}"
                )
            else:
                message = (
                    f"Notebook [**{self.widget.notebook_name}**]({self.widget.url}) "
                    f"**stopped** after execution **\\[{self.widget.jupyter_execution_num}\\]**:\n"
                    f"```python\n{self.widget.jupyter_cell_text}\n```\n\n"
                    f"Started: {started}\n\n"
                    f"Ended: {ended}"
                )

            response = await instance.notify(message=message, async_req=True, **kws)  # type: ignore
            LOGGER.info("Notification sent. Response: %s", response.to_dict())
            self.widget.sent_notifications = (
                self.widget.sent_notifications + [response.to_dict()]
            )[-100:]

    def _observe_jupyter(self, loop: asyncio.AbstractEventLoop) -> Callable[[], None]:
        def handle_jupyter_state_change(_, old_state, new_state):
            with background_ctx(LOGGER, type(self).__name__):
                self.widget.jupyter_state = new_state
                if (
                    new_state != IPythonShellState.Idle
                    or self.widget.monitoring_state == IPythonMonitoringState.None_
                ):
                    return

                now = ts_millis()
                if (
                    self.widget.notify_min_execution is not None
                    and self.widget.jupyter_execution_num
                    < self.widget.notify_min_execution
                ) or (
                    self.widget.notify_min_time is not None
                    and now < self.widget.notify_min_time
                ):
                    return

                if (
                    self.widget.monitoring_state == IPythonMonitoringState.Error
                    and self.widget.jupyter_cell_state == IPythonCellStateType.Error
                ):
                    task = loop.create_task(self._send_notification())
                    task.add_done_callback(self._handle_done_future)
                elif self.widget.monitoring_state == IPythonMonitoringState.Stop:
                    task = loop.create_task(self._send_notification())
                    task.add_done_callback(self._handle_done_future)
                self.widget.monitoring_state = IPythonMonitoringState.None_

        jupyter_state_changed.connect(handle_jupyter_state_change, sender=self.history)

        def handle_jupyter_cell_state_change(_, old_state, new_state):
            with background_ctx(LOGGER, type(self).__name__):
                # LOGGER.debug("State change %s %s", old_state, new_state)
                self.widget.jupyter_execution_num = new_state.execution_count
                self.widget.jupyter_cell_text = new_state.info.raw_cell
                state = IPythonCellStateType.Running
                error = None
                if new_state.result and new_state.error():
                    error_obj = new_state.error()
                    if isinstance(error_obj, KeyboardInterrupt):
                        state = IPythonCellStateType.Cancelled
                    else:
                        state = IPythonCellStateType.Error
                        error = f"{type(new_state.error()).__name__}: {str(new_state.error())}"
                elif new_state.result:
                    state = IPythonCellStateType.Success
                self.widget.jupyter_cell_state = state
                self.widget.jupyter_cell_started_at = ts_millis(new_state.started_at)
                finished_at = None
                if new_state.finished_at:
                    finished_at = ts_millis(new_state.finished_at)
                self.widget.jupyter_cell_finished_at = finished_at
                self.widget.jupyter_cell_error = error

        jupyter_cell_state_changed.connect(
            handle_jupyter_cell_state_change, sender=self.history
        )

        self.history.connect()

        def unobserve():
            self.history.disconnect()
            jupyter_state_changed.disconnect(
                handle_jupyter_state_change, sender=self.history
            )
            jupyter_cell_state_changed.disconnect(
                handle_jupyter_cell_state_change, sender=self.history
            )

        return unobserve

    def _observe_instance(self, loop: asyncio.AbstractEventLoop) -> Callable[[], None]:
        disconnected = False
        instance = get_instance()

        def connect(instance: Instance) -> None:
            self.widget.selected_channel = instance.default_channel
            self.widget.access_token = instance.access_token
            self.widget.api_url = instance.server_url
            self.widget.auth_url = None

            if instance.access_token:
                self.widget.auth_state = AuthState.Authenticated
            else:
                self.widget.auth_state = AuthState.NeedsAuth

            self.widget.channels_state = instance.channels.fetch_state
            if instance.channels.fetch_state == ChannelsState.Loaded:
                self.widget.channels = [
                    channel.to_dict() for channel in instance.channels
                ]
            else:
                self.widget.channels = []

        connect(instance)

        @default_channel_changed.connect
        def on_channel_changed(sender, old_value, new_value):
            LOGGER.debug("Default channel update: %s %s", old_value, new_value)
            nonlocal instance
            if sender is not instance:
                return
            with background_ctx(LOGGER, type(self).__name__):
                self.widget.selected_channel = new_value

        @access_token_changed.connect
        def on_access_token_changed(sender, old_value, new_value):
            nonlocal instance
            if sender is not instance:
                return

            with background_ctx(LOGGER, type(self).__name__):
                if old_value == new_value:
                    return
                self.widget.auth_state = (
                    AuthState.Authenticated if new_value else AuthState.NeedsAuth
                )
                self.widget.channels_state = ChannelsState.None_
                self.widget.channels = []
                self.widget.selected_channel = None
                self.widget.auth_url = None
                self.widget.access_token = new_value
                if new_value:
                    LOGGER.info("Initiating channel fetch")
                    task = loop.create_task(self.refresh_channels({}, instance))
                    task.add_done_callback(self._handle_done_future)

        @server_url_changed.connect
        def on_server_url_changed(sender, old_value, new_value):
            nonlocal instance
            if sender is not instance:
                return

            with background_ctx(LOGGER, type(self).__name__):
                if old_value == new_value:
                    return
                self.widget.api_url = new_value

        @default_instance_changed.connect
        def on_default_instance_changed(sender, old_instance, new_instance):
            nonlocal instance
            if instance is new_instance:
                return
            instance = new_instance
            with background_ctx(LOGGER, type(self).__name__):
                connect(instance)

        @channels_fetch_state_changed.connect
        def on_channels_state_changed(sender: Channels, old_value, new_value):
            LOGGER.debug(
                "Channels state update: %s %s %s", sender, old_value, new_value
            )
            nonlocal instance
            if sender.instance is not instance:
                return
            with background_ctx(LOGGER, type(self).__name__):
                self.widget.channels_state = new_value
                if new_value == ChannelsState.Loaded:
                    self.widget.channels = [channel.to_dict() for channel in sender]

        def unbind():
            nonlocal disconnected
            if disconnected:
                return
            channels_fetch_state_changed.disconnect(on_channels_state_changed)
            default_channel_changed.disconnect(on_channel_changed)
            access_token_changed.disconnect(on_access_token_changed)
            default_instance_changed.disconnect(on_default_instance_changed)
            server_url_changed.disconnect(on_server_url_changed)
            disconnected = True

        return unbind

    def _observe_notebook(self) -> Callable[[], None]:
        @notebook_name_changed.connect_via(self.info_watcher)
        def handle_name_change(sender, old_value, new_value):
            self.widget.notebook_name = new_value or "<unknown>"

        def unobserve():
            notebook_name_changed.disconnect(handle_name_change, self.info_watcher)

        return unobserve

    async def _observe_auth(self) -> None:
        while True:
            instance = get_instance()

            if not instance.access_token:
                await asyncio.wait(
                    [
                        wait_for_signal(access_token_changed, instance),
                        wait_for_signal(default_instance_changed),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                continue

            try:
                access_token = await instance._get_access_token_async()
            except exc.NotLoggedIn:
                access_token = None

            if access_token:
                try:
                    await api.get_current_app(  # type: ignore
                        async_req=True,
                        _headers={"Authorization": f"Bearer {access_token}"},
                    )
                except ApiException as err:
                    if 400 <= err.status < 500:
                        LOGGER.warn(
                            "Logging out because of %d response to get_current_app",
                            err.status,
                        )
                        instance.logout()
            elif self.widget.auth_state == AuthState.Authenticated:
                LOGGER.warn(
                    "Logging out because of no access token",
                )
                instance.logout()

            await asyncio.sleep(900)

    @contextlib.contextmanager
    def _session_ctx(self, loop: asyncio.AbstractEventLoop):
        instance = get_instance()

        lock = asyncio_lock(loop=loop)

        session: Optional[SessionResponse] = None

        connect_task: Optional[asyncio.Task] = None

        queue = asyncio_queue(loop=loop)

        def date_or_null(value):
            if not value:
                return None
            return date_from_millis(value).isoformat()

        def end_session():
            if session is None:
                return
            instance.end_session(session.session_id)

        async def sender(ws: WebSocket):
            while True:
                await queue.get()
                message_count = 1

                while not queue.empty():
                    queue.get_nowait()
                    message_count += 1

                LOGGER.info(
                    "Started: %s (%s), finished: %s (%s)",
                    self.widget.jupyter_cell_started_at,
                    date_or_null(self.widget.jupyter_cell_started_at),
                    self.widget.jupyter_cell_finished_at,
                    date_or_null(self.widget.jupyter_cell_finished_at),
                )

                message = {
                    "url": self.widget.url,
                    "notebookName": self.widget.notebook_name,
                    "shellState": self.widget.jupyter_state.value,
                    "cellState": self.widget.jupyter_cell_state.value,
                    "cellText": self.widget.jupyter_cell_text,
                    "cellError": self.widget.jupyter_cell_error,
                    "executionNum": self.widget.jupyter_execution_num,
                    "cellStartedAt": date_or_null(self.widget.jupyter_cell_started_at),
                    "cellFinishedAt": date_or_null(
                        self.widget.jupyter_cell_finished_at
                    ),
                    "notifyOn": self.widget.monitoring_state,
                    "notifyChannel": self.widget.selected_channel,
                }
                LOGGER.debug("Sending ws message: %s", message)
                await ws.send(message)
                LOGGER.debug("Sent ws message")

                for _ in range(message_count):
                    queue.task_done()

        async def receiver(ws: WebSocket):
            async for item in ws:
                if not item["ok"]:
                    LOGGER.error("Error in websocket: %s", item)
                    continue

                msg_type = item["message"]["type"]
                if msg_type == "update":
                    LOGGER.debug("Update from session: %s", item)
                    state = item["message"]["session"]["state"]
                    if self.widget.monitoring_state != state["notifyOn"]:
                        self.widget.monitoring_state = state["notifyOn"]
                    if state.get(
                        "notifyChannel"
                    ) and self.widget.selected_channel != state.get("notifyChannel"):
                        self.widget.selected_channel = state.get("notifyChannel")
                elif msg_type == "action":
                    action = item["message"]["action"]
                    if action == "interrupt":
                        os.kill(os.getpid(), signal.SIGINT)
                    else:
                        LOGGER.error("Invalid action: %s", action)
                else:
                    LOGGER.warn("Unhandled ws message type: %s", msg_type)

        async def connect():
            with background_ctx(LOGGER, type(self).__name__):
                if session is None:
                    raise RuntimeError("No session created yet")

                try:
                    async with instance.session_connect(
                        session.session_id, False
                    ) as ws:
                        await asyncio.gather(sender(ws), receiver(ws))
                finally:
                    await instance.end_session(session.session_id, async_req=True)

        def handle_change(info):
            async def handle():
                nonlocal session, connect_task

                with background_ctx(LOGGER, type(self).__name__):
                    if self.widget.auth_state != AuthState.Authenticated:
                        return
                    if self.widget.notebook_name is None:
                        return

                    async with lock:
                        LOGGER.debug("Acquired lock")
                        if session is not None:
                            await queue.put(info)
                            return

                        session = await instance.create_session(
                            self.widget.notebook_name,
                            state=JupyterSessionState(
                                type="jupyter",
                                url=self.widget.url,
                                notebookName=self.widget.notebook_name,
                                shellState=self.widget.jupyter_state.value,
                                cellError=self.widget.jupyter_cell_error,
                                executionNum=self.widget.jupyter_execution_num,
                                cellStartedAt=date_or_null(
                                    self.widget.jupyter_cell_started_at
                                ),
                                cellFinishedAt=date_or_null(
                                    self.widget.jupyter_cell_finished_at
                                ),
                                notifyOn=self.widget.monitoring_state,
                                notifyChannel=self.widget.selected_channel,
                            ),
                            async_req=True,
                        )
                        LOGGER.info("Created session: %s", session.session_id)
                        self.widget.session = session.to_dict()

                        connect_task = asyncio.create_task(connect())
                        connect_task.add_done_callback(self._handle_done_future)

                        atexit.register(end_session)

            task = loop.create_task(handle())
            task.add_done_callback(self._handle_done_future)

        watch_properties = [
            "auth_state",
            "notebook_name",
            "url",
            "jupyter_state",
            "jupyter_cell_state",
            "jupyter_cell_error",
            "jupyter_cell_started_at",
            "jupyter_cell_finished_at",
            "monitoring_state",
            "selected_channel",
        ]

        self.widget.observe(handle_change, watch_properties)

        try:
            yield
        finally:
            if connect_task is not None:
                connect_task.cancel()

                with contextlib.suppress(asyncio.CancelledError):
                    loop.run_until_complete(connect_task)

            self.widget.unobserve(handle_change, watch_properties)

    async def main_loop(self) -> None:
        while not self.shutdown_event.is_set():
            await asyncio.sleep(0.1)

    def run(self) -> None:
        with contextlib.ExitStack() as stack:
            stack.enter_context(background_ctx(LOGGER, type(self).__name__))
            stack.enter_context(loop_ctx(self.loop))
            stack.enter_context(self._session_ctx(self.loop))

            loop = self.loop
            unobserve_widget = self._observe_widget(loop)
            unobserve_instance = self._observe_instance(loop)
            unobserve_jupyter = self._observe_jupyter(loop)
            unobserve_notebook = self._observe_notebook()

            tasks = []
            tasks.append(loop.create_task(self.history.main_loop()))
            tasks.append(loop.create_task(self.info_watcher.main_loop()))
            tasks.append(loop.create_task(self._observe_auth()))
            tasks.append(loop.create_task(observe_google_colab_url(self.widget)))

            try:
                LOGGER.info("Starting main loop")
                self.startup_event.set()
                loop.run_until_complete(self.main_loop())
            finally:
                LOGGER.debug("Exiting")
                for task in reversed(tasks):
                    with contextlib.suppress(asyncio.CancelledError):
                        task.cancel()
                unobserve_notebook()
                unobserve_jupyter()
                unobserve_instance()
                unobserve_widget()
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()


DEFAULT_WIDGET = None

DEFAULT_WIDGET_LOCK = threading.RLock()


def get_widget() -> LMKWidget:
    global DEFAULT_WIDGET
    with DEFAULT_WIDGET_LOCK:
        if DEFAULT_WIDGET is None:
            DEFAULT_WIDGET = LMKWidget()
        return DEFAULT_WIDGET


def set_widget(widget: LMKWidget) -> None:
    global DEFAULT_WIDGET
    with DEFAULT_WIDGET_LOCK:
        if widget is DEFAULT_WIDGET:
            return
        if DEFAULT_WIDGET is not None:
            DEFAULT_WIDGET.shutdown()
        DEFAULT_WIDGET = widget
