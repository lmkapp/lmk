import asyncio
import configparser
import contextlib
import enum
import inspect
import json
import logging
import os
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict, AsyncContextManager

import aiohttp
from blinker import signal
from dateutil.parser import parse as parse_dt

from lmk import exc
from lmk.api_client import api_client
from lmk.constants import APP_ID, API_URL
from lmk.generated.api.event_api import EventApi
from lmk.generated.api.headless_auth_api import HeadlessAuthApi
from lmk.generated.api.notification_api import NotificationApi
from lmk.generated.api.session_api import SessionApi
from lmk.generated.exceptions import ApiException
from lmk.generated.models.access_token_response import AccessTokenResponse
from lmk.generated.models.create_headless_auth_session_request import (
    CreateHeadlessAuthSessionRequest,
)
from lmk.generated.models.create_session_request import CreateSessionRequest
from lmk.generated.models.event_request import (
    EventRequest,
    EventNotificationConfiguration,
)
from lmk.generated.models.event_response import EventResponse
from lmk.generated.models.headless_auth_refresh_token_request import (
    HeadlessAuthRefreshTokenRequest,
)
from lmk.generated.models.headless_auth_session_response import (
    HeadlessAuthSessionResponse,
)
from lmk.generated.models.notification_channel_response import (
    NotificationChannelResponse,
)
from lmk.generated.models.create_session_request_state import CreateSessionRequestState
from lmk.generated.models.session_response import SessionResponse
from lmk.jupyter import is_jupyter, run_javascript
from lmk.utils.asyncio import async_callback
from lmk.utils.ws import WebSocket, ws_connected


LOGGER = logging.getLogger(__name__)

default_instance_changed = signal("default-instance-changed")

access_token_changed = signal("access-token-changed")

server_url_changed = signal("server-url-changed")

default_channel_changed = signal("default-channel-changed")

channels_fetch_state_changed = signal("channels-fetch-state-changed")


class ChannelType(str, enum.Enum):
    """ """

    Email = "email"
    TextMessage = "text-message"


class ChannelsState(str, enum.Enum):
    None_ = "none"
    Loading = "loading"
    Forbidden = "forbidden"
    Loaded = "loaded"
    Error = "error"


def is_context_manager(obj: Any) -> bool:
    return hasattr(obj, "__enter__") and hasattr(obj, "__exit__")


def is_async_context_manager(obj: Any) -> bool:
    return hasattr(obj, "__aenter__") and hasattr(obj, "__aexit__")


def pipeline(is_async: bool = False) -> Any:
    """
    Basic abstraction to be able to write sync & async implementations
    of the same API methods with the same code--provide a sequence of functions
    that return either values or coroutines depending on is_async, and this
    will resolve them in order, passing each result to the next function
    in the pipeline
    """

    def sync_pipeline(*funcs, ctx_managers: List[Any] = ()):
        with contextlib.ExitStack() as stack:
            for ctx in ctx_managers:
                stack.enter_context(ctx)

            last_result = None
            for func in funcs:
                last_result = func(last_result)
            return last_result

    async def async_pipeline(*funcs, ctx_managers: List[Any] = ()):
        async with contextlib.AsyncExitStack() as stack:
            for ctx in ctx_managers:
                if is_async_context_manager(ctx):
                    await stack.enter_async_context(ctx)
                else:
                    stack.enter_context(ctx)

            last_result = None
            for func in funcs:
                last_result = func(last_result)
                if inspect.isawaitable(last_result):
                    last_result = await last_result
            return last_result

    return async_pipeline if is_async else sync_pipeline


def handle_error(is_async: bool = False) -> Any:
    """
    Similar to pipeline(), but for handling errors
    """

    def sync_handle_error(func, error_type, handle_error):
        try:
            return func()
        except error_type as err:
            return handle_error(err)

    async def async_handle_error(func, error_type, handle_error):
        try:
            return await func()
        except error_type as err:
            return handle_error(err)

    return async_handle_error if is_async else sync_handle_error


class Channels:
    """ """

    def __init__(self, instance: "Instance") -> None:
        self.instance = instance
        self._fetch_state = ChannelsState.None_
        self._fetch_lock = threading.Lock()
        self._afetch_lock = asyncio.Lock()
        self.data = None

        @access_token_changed.connect_via(instance)
        def handle_access_token_changed(sender, old_value, new_value):
            if not new_value:
                self.fetch_state = ChannelsState.None_
                self.data = None

    @property
    def fetch_state(self) -> ChannelsState:
        return self._fetch_state

    @fetch_state.setter
    def fetch_state(self, value: ChannelsState | str) -> None:
        if isinstance(value, str) and not isinstance(value, ChannelsState):
            value = ChannelsState(value)
        if value == self._fetch_state:
            return
        old_value, self._fetch_state = self._fetch_state, value
        channels_fetch_state_changed.send(self, old_value=old_value, new_value=value)

    def _ensure_fetched(self, fetch: bool = False, async_req: bool = False) -> None:
        if self.fetch_state != ChannelsState.Loaded and not fetch:
            raise Exception

        def maybe_fetch():
            if self.fetch_state != ChannelsState.Loaded and fetch:
                return self.fetch(async_req=async_req)
            return None

        def check():
            if self.fetch_state != ChannelsState.Loaded:
                raise exc.ChannelsNotFetched(self.fetch_state)

        return pipeline(async_req)(lambda _: maybe_fetch(), lambda _: check())

    @property
    def default(self) -> Optional[str]:
        return self.instance.default_channel

    @default.setter
    def default(self, value: Optional[str | NotificationChannelResponse]) -> None:
        self.instance.default_channel = value

    def fetch(self, async_req: bool = False, force: bool = False) -> None:
        ctx_managers = []
        if async_req:
            ctx_managers.append(self._afetch_lock)
        ctx_managers.append(self._fetch_lock)

        if (
            self.fetch_state
            not in {ChannelsState.None_, ChannelsState.Error, ChannelsState.Forbidden}
            and not force
        ):
            return

        self.fetch_state = ChannelsState.Loading

        def handle_channels(channels: List[NotificationChannelResponse]):
            LOGGER.debug("Channels: %s", channels)
            self.data = channels
            if channels:
                self.default = channels[0].notification_channel_id
            else:
                self.default = None
            self.fetch_state = ChannelsState.Loaded

        def handle_error_value(error: Exception):
            if isinstance(error, ApiException) and error.status == 403:
                self.fetch_state = ChannelsState.Forbidden
            else:
                self.fetch_state = ChannelsState.Error
            raise error

        error_handler = handle_error(async_req)

        return error_handler(
            lambda: pipeline(async_req)(
                lambda _: self.instance.list_notification_channels(async_req),
                handle_channels,
                ctx_managers=ctx_managers,
            ),
            Exception,
            handle_error_value,
        )

    def __repr__(self) -> str:
        if self.fetch_state != ChannelsState.Loaded:
            return f"{type(self).__name__}(fetch_state={self.fetch_state})"
        if not self.data:
            return f"{type(self).__name__}(<no channels>)"

        channel_strs = []
        for channel in self.data:
            is_default = channel.notification_channel_id == self.default
            prefix = "*" if is_default else " "
            channel_strs.append(
                " ".join(
                    [
                        " ",
                        prefix,
                        channel.name,
                        f"({channel.payload.actual_instance.type})",
                    ]
                )
            )

        channels_str = "\n".join(channel_strs)

        return f"{type(self).__name__}(\n{channels_str}\n)"

    def __iter__(self):
        self._ensure_fetched(fetch=True)
        yield from self.data

    async def __aiter__(self):
        await self._ensure_fetched(fetch=True, async_req=True)
        for channel in self.data:
            yield channel

    def list(
        self,
        name: str | None = None,
        type: str | ChannelType | None = None,
        name_exact: bool = False,
        fetch: bool = True,
        async_req: bool = False,
    ) -> List[NotificationChannelResponse]:
        if isinstance(type, str) and not isinstance(type, ChannelType):
            type = ChannelType(type)

        def filter():
            channels = self.data
            if type is not None:
                channels = [
                    c for c in channels if c.payload.actual_instance.type == type.value
                ]
            if name is not None and name_exact:
                channels = [c for c in channels if c.name == name]
            if name is not None and not name_exact:
                channels = [c for c in channels if name in c.name.lower()]
            return channels

        return pipeline(async_req)(
            lambda _: self._ensure_fetched(fetch=fetch, async_req=async_req),
            lambda _: filter(),
        )

    def get(
        self,
        name: str | None = None,
        type: str | ChannelType | None = None,
        name_exact: bool = False,
        fetch: bool = True,
        async_req: bool = False,
    ) -> NotificationChannelResponse | None:
        def pick(channels):
            if len(channels) > 1:
                raise exc.MultipleChannelsMatched(channels)
            if len(channels) == 0:
                return None
            return channels[0]

        return pipeline(async_req)(
            lambda _: self.list(
                name=name,
                type=type,
                name_exact=name_exact,
                fetch=fetch,
                async_req=async_req,
            ),
            pick,
        )


class Instance:
    """ """

    def __init__(
        self,
        profile: Optional[str] = None,
        server_url: Optional[str] = None,
        config_path: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        access_token_expires: Optional[datetime] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if profile is None:
            profile = os.getenv("LMK_PROFILE")
        if profile is None:
            profile = "python"
        if config_path is None:
            config_path = os.getenv("LMK_CONFIG_PATH")
        if access_token is None:
            access_token = os.getenv("LMK_ACCESS_TOKEN")
        if refresh_token is None:
            refresh_token = os.getenv("LMK_REFRESH_TOKEN")
        if access_token_expires is None:
            access_token_expires = os.getenv("LMK_ACCESS_TOKEN_EXPIRES")
        if server_url is None:
            server_url = os.getenv("LMK_SERVER_URL")
        if logger is None:
            logger = LOGGER

        if isinstance(access_token_expires, str) and access_token_expires.isdigit():
            access_token_expires = int(access_token_expires)
        elif isinstance(access_token_expires, str):
            access_token_expires = parse_dt(access_token_expires)

        if isinstance(access_token_expires, datetime):
            access_token_expires = int(access_token_expires.timestamp() * 1000)

        self._config_loaded = False
        self._access_token = None
        self._server_url = API_URL
        self._default_channel = None

        self.client = api_client(
            server_url=server_url or API_URL,
            logger=logger,
        )
        self.channels = Channels(self)

        self.profile = profile
        self.config_path = config_path
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.access_token_expires = access_token_expires
        self.server_url = server_url

        self._load_config()

    def close(self) -> None:
        self.client.close()

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    @access_token.setter
    def access_token(self, value: Optional[str]) -> None:
        if value == self.access_token:
            return
        old_value, self._access_token = self._access_token, value
        access_token_changed.send(self, old_value=old_value, new_value=value)

    @property
    def server_url(self) -> str:
        return self._server_url

    @server_url.setter
    def server_url(self, value: str) -> None:
        if value == self.server_url:
            return
        old_value, self._server_url = self._server_url, value
        self.client.configuration.host = value
        server_url_changed.send(
            self,
            old_value=old_value,
            new_value=value,
        )

    @property
    def default_channel(self) -> Optional[str]:
        return self._default_channel

    @default_channel.setter
    def default_channel(
        self, value: Optional[str | NotificationChannelResponse]
    ) -> None:
        LOGGER.debug(
            "Setting default channel; Current: %s, new: %s", self.default_channel, value
        )
        if isinstance(value, NotificationChannelResponse):
            value = value.notification_channel_id
        if value == self._default_channel:
            return
        old_value, self._default_channel = self._default_channel, value
        default_channel_changed.send(
            self,
            old_value=old_value,
            new_value=value,
        )

    def _load_config(self, force: bool = False) -> None:
        if self._config_loaded and not force:
            return

        parser = configparser.ConfigParser()
        if self.config_path is None:
            config_paths = [
                "./.lmk",
                os.path.expanduser("~/.lmk/config"),
            ]
        elif not os.path.isfile(self.config_path):
            raise exc.ConfigFileNotFound(self.config_path)
        else:
            config_paths = [self.config_path]

        parser.read(config_paths)
        if self.profile in parser:
            section = parser[self.profile]
            if self.access_token is None:
                self.access_token = section.get("access_token", self.access_token)
            if self.refresh_token is None:
                self.refresh_token = section.get("refresh_token", self.refresh_token)
            if self.access_token_expires is None:
                self.access_token_expires = section.getint(
                    "access_token_expires", self.access_token_expires
                )
            if self.server_url is None:
                self.server_url = section.get("server_url", self.server_url)

        if self.server_url is None:
            self.server_url = API_URL

        self._config_loaded = True

    def _save_config(self) -> None:
        config_path = self.config_path
        if config_path is None:
            config_path = os.path.expanduser("~/.lmk/config")

        config_dir = os.path.dirname(config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        parser = configparser.ConfigParser()
        obj = {}
        if self.access_token is not None:
            obj["access_token"] = self.access_token
        if self.refresh_token is not None:
            obj["refresh_token"] = self.refresh_token
        if self.access_token_expires is not None:
            obj["access_token_expires"] = self.access_token_expires
        if self.server_url is not None and self.server_url != API_URL:
            obj["server_url"] = self.server_url

        parser[self.profile] = obj
        with open(config_path, "w+") as f:
            parser.write(f)

        LOGGER.info("wrote config to %s", config_path)

        self._config_loaded = True

    def _refresh_access_token_sync(self) -> None:
        api = HeadlessAuthApi(self.client)
        response = api.refresh_headless_auth_token(
            HeadlessAuthRefreshTokenRequest(
                app_id=APP_ID, refresh_token=self.refresh_token
            )
        )
        self.set_access_token(
            response.access_token,
            self.refresh_token,
            datetime.utcnow() + timedelta(seconds=response.expires_in),
        )

    def _get_access_token_sync(self) -> str:
        now = datetime.utcnow().timestamp() * 1000
        if self.access_token_expires and self.access_token_expires < now:
            self._refresh_access_token_sync()
        if self.access_token is None:
            raise exc.NotLoggedIn()

        return self.access_token

    async def _refresh_access_token_async(self) -> None:
        api = HeadlessAuthApi(self.client)
        response = await api.refresh_headless_auth_token(
            HeadlessAuthRefreshTokenRequest(
                app_id=APP_ID, refresh_token=self.refresh_token
            ),
            async_req=True,
        )
        self.set_access_token(
            response.access_token,
            self.refresh_token,
            datetime.utcnow() + timedelta(seconds=response.expires_in),
        )

    async def _get_access_token_async(self) -> str:
        now = datetime.utcnow().timestamp() * 1000
        if self.access_token_expires and self.access_token_expires < now:
            await self._refresh_access_token_async()
        if self.access_token is None:
            raise exc.NotLoggedIn()

        return self.access_token

    def _get_access_token(self, async_req: bool = False) -> str:
        if async_req:
            return self._get_access_token_async()
        return self._get_access_token_sync()

    def logged_in(self) -> bool:
        return bool(self.access_token)

    def logout(self) -> None:
        """
        Get rid of the current access token and remove it from
        """
        self.access_token = None
        self.refresh_token = None
        self.access_token_expires = None
        self._save_config()

    def initiate_auth(
        self, scope: Optional[str] = None, async_req: bool = False
    ) -> HeadlessAuthSessionResponse:
        if scope is None:
            scope = "event.publish event.notify channel.read session.create"

        api = HeadlessAuthApi(self.client)
        return api.create_headless_auth_session(
            CreateHeadlessAuthSessionRequest(app_id=APP_ID, scope=scope),
            async_req=async_req,
        )

    def retrieve_auth_token(
        self, session_id: str, async_req: bool = False
    ) -> AccessTokenResponse:
        api = HeadlessAuthApi(self.client)
        handler = handle_error(async_req)

        def handle_api_exception(err):
            if err.status == 410:
                raise exc.AccessTokenAlreadyRetrieved(session_id) from err
            if err.status == 412:
                raise exc.AuthSessionNotComplete(session_id)
            raise err

        return handler(
            lambda: api.retrieve_headless_auth_session_token(
                session_id=session_id,
                async_req=async_req,
            ),
            ApiException,
            handle_api_exception,
        )

    def set_access_token(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        access_token_expires: Optional[datetime] = None,
        save: bool = True,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.access_token_expires = access_token_expires
        if isinstance(self.access_token_expires, datetime):
            self.access_token_expires = int(
                self.access_token_expires.timestamp() * 1000
            )
        if save:
            self._save_config()

    def login(
        self,
        scope: Optional[str] = None,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
        auth_mode: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """
        Authenticate LMK interactively. If possible, this will open
        a new auth session in a web browser. If not, it will print the
        auth URL and you will have to navigate to it in a browser manually

        auth_mode: jupyter, browser, manual. Will choose the first of those
        three that is available in the current context if None
        """
        if self.logged_in() and not force:
            print("Already authenticated, pass force=True to re-authenticate")
            return

        session = self.initiate_auth(scope)

        if auth_mode is None and is_jupyter():
            auth_mode = "jupyter"

        if auth_mode is None:
            try:
                # This will raise if none is available
                webbrowser.get()
                auth_mode = "browser"
            except webbrowser.Error:
                LOGGER.debug("No web browser available")

        if auth_mode is None:
            auth_mode = "manual"

        if auth_mode == "jupyter":
            run_javascript(f"window.open({json.dumps(session.authorize_url)})")
        elif auth_mode == "browser":
            webbrowser.open(session.authorize_url)
        elif auth_mode == "manual":
            print(
                f"Authenticate in a web browser by navigating to {session.authorize_url}"
            )
        else:
            raise RuntimeError(
                f"Invalid auth_mode: {auth_mode}, options: manual, browser, jupyter"
            )

        start = time.time()
        while time.time() - start < timeout:
            try:
                response = self.retrieve_auth_token(session.session_id)
            except exc.AuthSessionNotComplete:
                time.sleep(poll_interval)
                continue
            else:
                self.set_access_token(
                    response.access_token,
                    response.refresh_token,
                    datetime.utcnow() + timedelta(seconds=response.expires_in),
                )
                break

        print("Authentication successful")

    def list_notification_channels(
        self, async_req: bool = False
    ) -> List[NotificationChannelResponse]:
        """
        List the notification channels that are available to send notifications to
        """
        api = NotificationApi(self.client)
        return pipeline(async_req)(
            lambda _: self._get_access_token(async_req),
            lambda access_token: api.list_notification_channels(
                async_req=async_req,
                _headers={"Authorization": f"Bearer {access_token}"},
            ),
            lambda response: response.channels,
        )

    def notify(
        self,
        message: str,
        content_type: str = "text/markdown",
        notification_channels: Optional[List[str | NotificationChannelResponse]] = None,
        notify: bool = True,
        async_req: bool = False,
    ) -> EventResponse:
        """
        Send a notification
        """
        api = EventApi(self.client)
        kws = {}
        if notify:
            notify_kws = {}
            if notification_channels is not None:
                channels = []
                for channel in notification_channels:
                    if isinstance(channel, NotificationChannelResponse):
                        channel = channel.notification_channel_id
                    channels.append(channel)
                notify_kws["channel_ids"] = channels
            elif self.default_channel:
                notify_kws["channel_ids"] = [self.default_channel]
            kws["notification_config"] = EventNotificationConfiguration(
                notify=True, **notify_kws
            )

        return pipeline(async_req)(
            lambda _: self._get_access_token(async_req),
            lambda access_token: api.post_event(
                EventRequest(message=message, content_type=content_type, **kws),
                async_req=async_req,
                _headers={"Authorization": f"Bearer {access_token}"},
            ),
        )

    def create_session(
        self,
        name: str,
        state: Dict[str, Any] = None,
        async_req: bool = False,
    ) -> SessionResponse:
        api = SessionApi(self.client)

        if isinstance(state, dict):
            state = CreateSessionRequestState.from_dict(state)
        else:
            state = CreateSessionRequestState(actual_instance=state)

        return pipeline(async_req)(
            lambda _: self._get_access_token(async_req),
            lambda access_token: api.create_session(
                CreateSessionRequest(
                    name=name,
                    state=state,
                ),
                async_req=async_req,
                _headers={"Authorization": f"Bearer {access_token}"},
            ),
        )

    def end_session(
        self,
        session_id: str,
        async_req: bool = False,
    ) -> None:
        api = SessionApi(self.client)

        return pipeline(async_req)(
            lambda _: self._get_access_token(async_req),
            lambda access_token: api.end_session(
                session_id, _headers={"Authorization": f"Bearer {access_token}"}
            ),
        )

    @contextlib.asynccontextmanager
    async def session_connect(
        self, session_id: str, read_only: bool = True
    ) -> AsyncContextManager[WebSocket]:
        access_token = await self._get_access_token_async()

        url = self.client.configuration.host + f"/v1/session/ws?token={access_token}"

        loop = asyncio.get_running_loop()

        async def on_connect(ws: WebSocket):
            LOGGER.debug("Session websocket connected for %s", session_id)
            await ws.send(
                {
                    "event": "connect",
                    "data": {"sessionId": session_id, "readOnly": read_only},
                }
            )
            LOGGER.debug("Sent connected message for %s", session_id)

        on_connect_cb = async_callback(on_connect, loop=loop)

        async with aiohttp.ClientSession(conn_timeout=10) as session:
            async with WebSocket(session, url, timeout=0.5, heartbeat=1) as ws:
                await on_connect(ws)

                ws_connected.connect(on_connect_cb, ws)
                try:
                    yield ws
                finally:
                    ws_connected.disconnect(on_connect_cb, ws)


DEFAULT_INSTANCE = None

DEFAULT_INSTANCE_LOCK = threading.RLock()


def get_instance() -> Instance:
    global DEFAULT_INSTANCE
    with DEFAULT_INSTANCE_LOCK:
        if DEFAULT_INSTANCE is None:
            DEFAULT_INSTANCE = Instance()
        return DEFAULT_INSTANCE


def set_instance(instance: Instance) -> None:
    global DEFAULT_INSTANCE
    with DEFAULT_INSTANCE_LOCK:
        if DEFAULT_INSTANCE is instance:
            return
        if DEFAULT_INSTANCE is not None:
            DEFAULT_INSTANCE.close()
        DEFAULT_INSTANCE, old_instance = instance, DEFAULT_INSTANCE
        default_instance_changed.send(
            set_instance,
            old_instance=old_instance,
            new_instance=instance,
        )
