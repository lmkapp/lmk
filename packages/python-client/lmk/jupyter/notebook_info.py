# This was originally copied from the source code of the ipynbname package,
# didn't want to add a dependency for this relatively simple functionality
# source: https://github.com/msm1089/ipynbname/blob/master/ipynbname/__init__.py
import asyncio
import json
import logging
import os
from itertools import chain
from pathlib import Path
from typing import Generator, Tuple, Union, NoReturn, Optional, Dict, Any, List
from urllib.parse import urljoin

import aiohttp
import ipykernel
from blinker import signal
from jupyter_core.paths import jupyter_runtime_dir
from traitlets.config import MultipleInstanceError


LOGGER = logging.getLogger(__name__)

notebook_name_changed = signal("notebook-name-changed")

FILE_ERROR = "Can't identify the notebook name."


def _list_maybe_running_servers(runtime_dir=None) -> Generator[dict, None, None]:
    """Iterate over the server info files of running notebook servers."""
    if runtime_dir is None:
        runtime_dir = jupyter_runtime_dir()
    runtime_dir = Path(runtime_dir)

    if runtime_dir.is_dir():
        for file_name in chain(
            runtime_dir.glob("nbserver-*.json"),  # jupyter notebook (or lab 2)
            runtime_dir.glob("jpserver-*.json"),  # jupyterlab 3
        ):
            yield json.loads(file_name.read_bytes())


def _get_kernel_id() -> str:
    """Returns the kernel ID of the ipykernel."""
    connection_file = Path(ipykernel.get_connection_file()).stem
    kernel_id = connection_file.split("-", 1)[1]
    return kernel_id


def kernel_id() -> Optional[str]:
    try:
        return _get_kernel_id()
    except (MultipleInstanceError, RuntimeError):
        LOGGER.debug("Unable to get the current kernel ID", exc_info=True)
        return None


async def _get_sessions(
    srv: Dict[str, Any], session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """Given a server, returns sessions, or HTTPError if access is denied.
    NOTE: Works only when either there is no security or there is token
    based security. An HTTPError is raised if unable to connect to a
    server.
    """
    url = srv["url"]
    token = srv.get("token")
    sessions_url = urljoin(url, "/api/sessions")

    # If no token, just try to make a request once
    if not token:
        response = await session.get(sessions_url)
        response.raise_for_status()
        return await response.json()

    # If there is a token, we try two approaches: first use the token in a header,
    # then try using a query param.
    response = await session.get(f"{sessions_url}?token={token}")
    try:
        response.raise_for_status()
        return await response.json()
    except aiohttp.ClientResponseError:
        pass

    response = await session.get(
        sessions_url, headers={"Authorization": f"token {token}"}
    )
    response.raise_for_status()

    return await response.json()


async def find_server_and_session(
    session: aiohttp.ClientSession,
) -> (Union[Tuple[Dict[str, Any], Dict[str, Any]], Tuple[None, None]]):
    """
    Find the server and session for the current Jupyter kernel
    """
    try:
        kernel_id = _get_kernel_id()
    except (MultipleInstanceError, RuntimeError):
        LOGGER.debug("Unable to get the current kernel ID", exc_info=True)
        return None, None  # Could not determine
    for srv in _list_maybe_running_servers():
        try:
            sessions = await _get_sessions(srv, session)
            for sess in sessions:
                if sess["kernel"]["id"] == kernel_id:
                    return srv, sess
        except Exception:
            # There may be stale entries in the runtime directory, so this
            # is expected to happen sometimes
            LOGGER.debug("Error getting sessions for server %r", srv, exc_info=True)
    return None, None


async def notebook_name(client_session: aiohttp.ClientSession) -> str:
    """Returns the short name of the notebook w/o the .ipynb extension,
    or raises a FileNotFoundError exception if it cannot be determined.
    """
    from lmk.jupyter.colab import colab_support_enabled

    _, session = await find_server_and_session(client_session)
    if session is None:
        raise FileNotFoundError(FILE_ERROR)

    if colab_support_enabled():
        session_name = session.get("notebook", {}).get("name")
        if session_name:
            return session_name

    path = session.get("notebook", {}).get("path")
    if path is None:
        raise FileNotFoundError(FILE_ERROR)

    return os.path.basename(path)


class NotebookInfoWatcher:
    """
    Periodically query the jupyter server to see if the notebook name has changed
    """

    def __init__(self, poll_interval: float = 30.0) -> None:
        self.poll_interval = poll_interval
        self.notebook_name: Optional[str] = None

    async def refresh(self) -> None:
        async with aiohttp.ClientSession() as session:
            current_name = await notebook_name(session)
            if current_name == self.notebook_name:
                return
            self.notebook_name, old_name = current_name, self.notebook_name
            notebook_name_changed.send(self, old_value=old_name, new_value=current_name)

    async def main_loop(self) -> NoReturn:
        while True:
            try:
                await self.refresh()
            except Exception:
                LOGGER.warn("Error getting notebook name", exc_info=True)
            await asyncio.sleep(self.poll_interval)
