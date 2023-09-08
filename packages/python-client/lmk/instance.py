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
from typing import (
    Optional,
    List,
    Any,
    Dict,
    AsyncGenerator,
    Union,
    Awaitable,
    cast,
    ContextManager,
    AsyncContextManager,
)

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
from lmk.generated.models.process_session_state import ProcessSessionState
from lmk.generated.models.jupyter_session_state import JupyterSessionState
from lmk.generated.models.session_response import SessionResponse
from lmk.jupyter import is_jupyter, run_javascript
from lmk.utils.asyncio import async_callback, asyncio_lock
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

    def sync_pipeline(*funcs, ctx_managers: List[Any] = []):
        with contextlib.ExitStack() as stack:
            for ctx in ctx_managers:
                stack.enter_context(ctx)

            last_result = None
            for func in funcs:
                last_result = func(last_result)
            return last_result

    async def async_pipeline(*funcs, ctx_managers: List[Any] = []):
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
    """
    An instance of this class is available at the top level of the ``lmk`` module under the
    ``lmk.channels`` attribute. This class's function is to simplify fetching and searching
    for notification channels. Channels are always fetched lazily when required based on
    ``get()``, ``list()``, or iterating through the ``channels`` object (synchronously or
    asynchronously).

    <details><summary>Usage Example</summary>
    <p>

    ```python
    import lmk

    # Check that the client is logged in (optional)
    # If using for the first time on a new device, call lmk.login()
    assert lmk.logged_in()

    # Get an email notification channel
    channel = lmk.channels.get(type="email")
    # Get a text message notification channel asynchronously
    channel = await lmk.channels.get(type="text-message", async_req=True)

    # Iterate through notification channels
    for channel in lmk.channels:
        print(channel)

    # Iterate through notification channels asynchronously
    async for channel in lmk.channels:
        print(channel)
    ```
    </p>
    </details>
    """

    def __init__(self, instance: "Instance") -> None:
        self.instance = instance
        self._fetch_state = ChannelsState.None_
        self._fetch_lock = threading.Lock()
        self._afetch_lock = asyncio_lock()
        self.data: Optional[List[NotificationChannelResponse]] = None

        @access_token_changed.connect_via(instance)
        def handle_access_token_changed(sender, old_value, new_value):
            if not new_value:
                self.fetch_state = ChannelsState.None_
                self.data = None

    @property
    def fetch_state(self) -> ChannelsState:
        return self._fetch_state

    @fetch_state.setter
    def fetch_state(self, value: Union[ChannelsState, str]) -> None:
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
        """
        The default notification channel; If ``notify()`` is called without passing
        ``notification_channels``, the notification will be sent to this channel. If you
        do not set this value, it will be set to the default notification channel for
        your account.

        <details><summary>Usage Example</summary>
        <p>

        ```python
        import lmk

        lmk.channels.default = lmk.channels.get(type="text-message")
        ```

        </p>
        </details>
        """
        return self.instance.default_channel

    @default.setter
    def default(self, value: Optional[Union[str, NotificationChannelResponse]]) -> None:
        self.instance.default_channel = value  # type: ignore

    def fetch(self, async_req: bool = False, force: bool = False) -> None:
        """
        Fetch notification channels.

        **Note:** This requires the client to be logged in.

        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional
        :param force: If ``True``, refetch notification channels even if they have already
        been fetched successfully. By default, fetching will be skipped if it's already been done
        successfully.

        :return: This method does not return anything
        :rtype: None
        """
        ctx_managers: List[Union[ContextManager[Any], AsyncContextManager[Any]]] = []
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
        name: Optional[str] = None,
        type: Optional[Union[str, ChannelType]] = None,
        name_exact: bool = False,
        fetch: bool = True,
        async_req: bool = False,
    ) -> List[NotificationChannelResponse]:
        """
        List notification channels. This will fetch notification channels if they haven't been
        fetched yet.

        :param name: Filter down to notification channels with the given name
        :type name: str, optional
        :param name_exact: Only return channels whose names exactly match ``name``. By default,
        the name matching is case insensitive.
        :type name_exact: bool, optional
        :param type: Filter to only notification channels of this type
        :type type: str | ChannelType, optional
        :param fetch: Fetch notification channels if they haven't been fetched yet.
        :type fetch: bool, optional
        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional

        :return: A list of notification channels matching the given parameters
        :rtype: List[NotificationChannelResponse]
        """
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
        name: Optional[str] = None,
        type: Optional[Union[str, ChannelType]] = None,
        name_exact: bool = False,
        fetch: bool = True,
        async_req: bool = False,
    ) -> Optional[NotificationChannelResponse]:
        """
        Get a single notification channel with the given parameters.

        :param name: Filter down to notification channels with the given name
        :type name: str, optional
        :param name_exact: Only return channels whose names exactly match ``name``. By default,
        the name matching is case insensitive.
        :type name_exact: bool, optional
        :param type: Filter to only notification channels of this type
        :type type: str | ChannelType, optional
        :param fetch: Fetch notification channels if they haven't been fetched yet.
        :type fetch: bool, optional
        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional

        :return: A notification channel matching the given parameters, or ``None`` if none exists.
        :rtype: NotificationChannelResponse | None
        """

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

    access_token_expires: Optional[int]

    def __init__(
        self,
        profile: Optional[str] = None,
        server_url: Optional[str] = None,
        config_path: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        access_token_expires: Optional[Union[datetime, str]] = None,
        logger: Optional[logging.Logger] = None,
        sync_config: bool = True,
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

        access_token_expires_value: Optional[int]
        if isinstance(access_token_expires, str) and access_token_expires.isdigit():
            access_token_expires_value = int(access_token_expires)
        elif isinstance(access_token_expires, str):
            access_token_expires = parse_dt(access_token_expires)

        if isinstance(access_token_expires, datetime):
            access_token_expires_value = int(access_token_expires.timestamp() * 1000)
        if access_token_expires is None:
            access_token_expires_value = None

        self._config_loaded: bool = False
        self._access_token: Optional[str] = None
        self._server_url: Optional[str] = None
        self._default_channel: Optional[str] = None

        self.client = api_client(
            server_url=server_url or API_URL,
            logger=logger,
        )
        self.channels = Channels(self)

        # Set this to False before loading initial values so that we
        # don't overwrite things.
        self.sync_config = False

        self.profile = profile
        self.config_path = config_path
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.access_token_expires = access_token_expires_value
        self.server_url = cast(str, server_url)
        self.sync_config = sync_config

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
        return self._server_url or API_URL

    @server_url.setter
    def server_url(self, value: Optional[str]) -> None:
        if value == self._server_url:
            return
        old_value, self._server_url = self._server_url, value

        self.client.configuration.host = value
        server_url_changed.send(
            self,
            old_value=old_value,
            new_value=value,
        )
        if self.sync_config:
            self._save_config()

    @property
    def default_channel(self) -> Optional[str]:
        return self._default_channel

    @default_channel.setter
    def default_channel(
        self, value: Optional[Union[str, NotificationChannelResponse]]
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

    def _load_config(self, force: bool = False, overwrite: bool = False) -> None:
        if self._config_loaded and not force:
            return

        parser = configparser.ConfigParser()
        if self.config_path is None:
            config_paths = [os.path.expanduser("~/.lmk/config")]
        elif not os.path.isfile(self.config_path):
            raise exc.ConfigFileNotFound(self.config_path)
        else:
            config_paths = [self.config_path]

        read_config_paths = [path for path in config_paths if os.path.isfile(path)]

        parser.read(read_config_paths)
        if self.profile in parser:
            section = parser[self.profile]
            if self.access_token is None or overwrite:
                self.access_token = section.get("access_token", self.access_token)
            if self.refresh_token is None or overwrite:
                self.refresh_token = section.get("refresh_token", self.refresh_token)
            if self.access_token_expires is None or overwrite:
                self.access_token_expires = section.getint(
                    "access_token_expires", self.access_token_expires
                )
            if self._server_url is None or overwrite:
                self.server_url = section.get("server_url", self._server_url)

        self._config_loaded = True

    def _save_config(self) -> None:
        config_path = self.config_path
        if config_path is None:
            config_path = os.path.expanduser("~/.lmk/config")

        config_dir = os.path.dirname(config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        parser = configparser.ConfigParser()
        obj: Dict[str, Any] = {}
        if self.access_token is not None:
            obj["access_token"] = self.access_token
        if self.refresh_token is not None:
            obj["refresh_token"] = self.refresh_token
        if self.access_token_expires is not None:
            obj["access_token_expires"] = self.access_token_expires
        if self._server_url is not None:
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
                appId=APP_ID, refreshToken=cast(str, self.refresh_token)
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
        response = await api.refresh_headless_auth_token(  # type: ignore
            HeadlessAuthRefreshTokenRequest(
                appId=APP_ID, refreshToken=cast(str, self.refresh_token)
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

    def _get_access_token(self, async_req: bool = False) -> Union[str, Awaitable[str]]:
        if async_req:
            return self._get_access_token_async()
        return self._get_access_token_sync()

    def logged_in(self) -> bool:
        """
        Check whether the client is currently logged in

        :return: a boolean indicating if you are logged in or not
        :rtype: bool
        """
        return bool(self.access_token)

    def logout(self) -> None:
        """
        Get rid of the current access token. After calling this, you will
        need to log in again in order to use methods that require authentication
        such as ``notify()``

        :return: This method does not return anything
        :rtype: None
        """
        self.access_token = None
        self.refresh_token = None
        self.access_token_expires = None
        if self.sync_config:
            self._save_config()

    def initiate_auth(
        self, scope: Optional[str] = None, async_req: bool = False
    ) -> HeadlessAuthSessionResponse:
        if scope is None:
            scope = "event.publish event.notify channel.read session.create"

        api = HeadlessAuthApi(self.client)
        return api.create_headless_auth_session(
            CreateHeadlessAuthSessionRequest(appId=APP_ID, scope=scope),
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
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        if isinstance(access_token_expires, datetime):
            self.access_token_expires = int(access_token_expires.timestamp() * 1000)
        else:
            self.access_token_expires = access_token_expires
        if self.sync_config:
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

        :param auth_mode: ``jupyter``, ``browser`` or ``manual``. If ``None``, the first of those
        three that is available in the current context will be chosen automatically.
        :type auth_mode: str, optional
        :param scope: If desired, you may manually specify scopes that the retrieved access token
        should have, separated by spaces. If ``None``, all scopes will be requested. The user may
        modify these scopes during the OAuth flow to make them more restrictive.
        :type scope: str, optional
        :param timeout: A float indicating how long the client should wait for authentication to
        succeed before considering the authentication attempt failed.
        :type timeout: float, optional
        :param poll_interval: The poll interval for checking if the created authentication
        session has succeeded.
        :type poll_interval: float, optional
        :param force: By default if you are already logged in, this method will simply
        return immediately. By passing ``force=True``, you may force the client to replace
        the current authentication information and log in again.
        :type force: bool, optional

        :return: This method does not return anything
        :rtype: None
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

        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional

        :return: A list of notification channels that the current client has access to.
        :rtype: List[NotificationChannelResponse]
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
        notification_channels: Optional[
            List[Union[str, NotificationChannelResponse]]
        ] = None,
        notify: bool = True,
        async_req: bool = False,
    ) -> EventResponse:
        """
        Send a notification to one of your configured notification channels.

        **Note:** This method requires you to be [logged in](#login) to LMK.

        <details><summary>Usage Example</summary>
        <p>

        ```python
        import lmk

        # Check that the client is logged in (optional)
        # If using for the first time on a new device, call lmk.login()
        assert lmk.logged_in()

        lmk.notify("Hello, world!")
        ```

        </p>
        </details>

        :param message: The content of the notification you want to send
        :type message: str
        :param content_type: The MIME type of the message you want to send; ``text/plain`` and
        ``text/markdown`` are supported. Defaults to ``text/markdown``
        :type content_type: str, optional
        :param notification_channels: A list of notification channel IDs or notification channel
        objects that you want to send the notification to. If ``None`` and ``notify = True`` (the
        default), this will be sent to the default notification channel for your account, which is
        the primary email address associated with your account by default. Defaults to ``None``
        :type notification_channels: List[str | NotificationChannelResponse], optional
        :param notify: ``True`` if you want to send a notification to one or more of your configured
        notification channels. If ``False``, this notification will only be visible via the LMK web app.
        Defaults to ``True``
        :type notify: bool, optional
        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional

        :return: The event object corresponding to the sent notification
        :rtype: EventResponse
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
                EventRequest(message=message, contentType=content_type, **kws),  # type: ignore
                async_req=async_req,
                _headers={"Authorization": f"Bearer {access_token}"},
            ),
        )

    def create_session(
        self,
        name: str,
        state: Optional[
            Union[Dict[str, Any], ProcessSessionState, JupyterSessionState]
        ] = None,
        async_req: bool = False,
    ) -> SessionResponse:
        """
        Create an interactive session, which you can use to remotely monitor a process
        or Jupyter Notebook remotely via the LMK web app. You shouldn't have to use this
        method directly in normal usage, rather it will be invoed by

        **Note:** This method requires you to be [logged in](#login) to LMK.

        :param name: The name of the session. This will appear in the LMK app.
        :type name: str
        :param state: The initial state parameters for the session. The ``type``
        field is always required, but the rest of the required fields depend on what
        type of session it is. See the REST API documentation for more information.
        :type state: Dict[str, Any]
        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional

        :return: The session object corresponding to the created session.
        :rtype: SessionResponse
        """
        api = SessionApi(self.client)

        if isinstance(state, dict):
            typed_state = CreateSessionRequestState.from_dict(state)
        else:
            typed_state = CreateSessionRequestState(actual_instance=state)  # type: ignore

        return pipeline(async_req)(
            lambda _: self._get_access_token(async_req),
            lambda access_token: api.create_session(
                CreateSessionRequest(
                    name=name,
                    state=typed_state,
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
        """
        End an interactive session. After the session has been ended, its state cannot
        be updated any more. Only call this when completely finished with using a session.

        :param session_id: The ID of a previously created session that has not been ended
        yet
        :type session_id: str
        :param async_req: ``True`` if you want to send the request asynchronously, in which case this
        method will return a coroutine. Defaults to ``False``.
        :type async_req: bool, optional

        :return: This method does not return anything
        :rtype: None
        """
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
    ) -> AsyncGenerator[WebSocket, None]:
        """
        Connect via a web socket to an interactive session. This allows you to send state
        updates to the session via a web socket, and receive remote state updates initiated
        through the LMK web app or API calls from other clients.

        :param session_id: the ID of a previously created session that has not been ended
        yet.
        :type session_id: str
        :param read_only: Indicate whether to connect in "read only" mode. This means that
        updates cannot be sent via the web socket, only received. Defaults to ``True``
        :type read_only: bool, optional

        :return: An asynchronous context manager yielding a ``WebSocket`` object
        :rtype: AsyncContextManager[WebSocket]
        """
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
