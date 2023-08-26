from typing import List

from lmk.generated.models.notification_channel_response import (
    NotificationChannelResponse,
)


class LMKError(Exception):
    """
    Base class for errors raised by LMK
    """


class ConfigFileNotFound(LMKError):
    """
    Error indicating that a configuration file that was manually specified
    was not found.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Config file does not exist: {path}")


class NotLoggedIn(LMKError):
    """
    Error indicating that you are trying to do something that required authentication,
    but the current client is not logged in
    """

    def __init__(self) -> None:
        super().__init__("The current client is not logged in.")


class AuthSessionNotComplete(LMKError):
    """
    Error indicating that an authentication session
    has not been completed yet
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session not complete yet: {session_id}")


class AccessTokenAlreadyRetrieved(LMKError):
    """
    Error indicating that the access token for an auth
    session has already been retrieved
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Access token already retrieved for session: {session_id}")


class AuthenticationTimeout(LMKError):
    """
    Error indicating that an interactive authentication session
    timed out
    """

    def __init__(self, session_id: str, timeout: float) -> None:
        self.session_id = session_id
        self.timeout = timeout
        super().__init__(
            f"Authentication timed out for session {session_id} after {timeout:.2f}s"
        )


class ChannelsNotFetched(LMKError):
    """
    Error indicating that you are trying to get channel information
    but it has not been fetched yet
    """

    def __init__(self, state: str) -> None:
        self.state = state
        super().__init__(f"Channels has not been fetched. State: {state}")


class MultipleChannelsMatched(LMKError):
    """
    Error indicating that get() was called on a Channels instance,
    but multiple channels matched query parameters
    """

    def __init__(self, channels: List[NotificationChannelResponse]) -> None:
        self.channels = channels
        channels_str = ", ".join([channel.name for channel in channels])
        super().__init__(f"Multiple channels matched parameters: {channels_str}")
