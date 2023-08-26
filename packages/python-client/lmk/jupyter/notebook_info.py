# This was originally copied from the source code of the ipynbname package,
# didn't want to add a dependency for this relatively simple functionality
# source: https://github.com/msm1089/ipynbname/blob/master/ipynbname/__init__.py
import asyncio
import json
import logging
import urllib.error
import urllib.request
from itertools import chain
from pathlib import Path, PurePath
from typing import Generator, Tuple, Union, NoReturn, Optional

import ipykernel
from blinker import signal
from jupyter_core.paths import jupyter_runtime_dir
from traitlets.config import MultipleInstanceError


LOGGER = logging.getLogger(__name__)

notebook_name_changed = signal("notebook-name-changed")

FILE_ERROR = "Can't identify the notebook {}."
CONN_ERROR = (
    "Unable to access server;\n"
    + "ipynbname requires either no security or token based security."
)


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
        return None


def _get_sessions(srv):
    """Given a server, returns sessions, or HTTPError if access is denied.
    NOTE: Works only when either there is no security or there is token
    based security. An HTTPError is raised if unable to connect to a
    server.
    """
    try:
        qry_str = ""
        token = srv["token"]
        if token:
            qry_str = f"?token={token}"
        url = f"{srv['url']}api/sessions{qry_str}"
        with urllib.request.urlopen(url) as req:
            return json.load(req)
    except Exception:
        raise urllib.error.HTTPError(CONN_ERROR)


def _find_nb_path() -> Union[Tuple[dict, PurePath], Tuple[None, None]]:
    try:
        kernel_id = _get_kernel_id()
    except (MultipleInstanceError, RuntimeError):
        return None, None  # Could not determine
    for srv in _list_maybe_running_servers():
        try:
            sessions = _get_sessions(srv)
            for sess in sessions:
                if sess["kernel"]["id"] == kernel_id:
                    return srv, PurePath(sess["notebook"]["path"])
        except Exception:
            pass  # There may be stale entries in the runtime directory
    return None, None


def notebook_name() -> str:
    """Returns the short name of the notebook w/o the .ipynb extension,
    or raises a FileNotFoundError exception if it cannot be determined.
    """
    _, path = _find_nb_path()
    if path:
        return path.name
    raise FileNotFoundError(FILE_ERROR.format("name"))


def notebook_path() -> Path:
    """Returns the absolute path of the notebook,
    or raises a FileNotFoundError exception if it cannot be determined.
    """
    srv, path = _find_nb_path()
    if srv and path:
        root_dir = Path(srv.get("root_dir") or srv["notebook_dir"])
        return root_dir / path
    raise FileNotFoundError(FILE_ERROR.format("path"))


class NotebookInfoWatcher:
    """ """

    def __init__(self, poll_interval: float = 30.0) -> None:
        self.poll_interval = poll_interval
        self.notebook_name = None

    def refresh(self) -> None:
        current_name = notebook_name()
        if current_name == self.notebook_name:
            return
        self.notebook_name, old_name = current_name, self.notebook_name
        notebook_name_changed.send(self, old_value=old_name, new_value=current_name)

    async def main_loop(self) -> NoReturn:
        loop = asyncio.get_running_loop()

        while True:
            await loop.run_in_executor(None, self.refresh)
            await asyncio.sleep(self.poll_interval)
