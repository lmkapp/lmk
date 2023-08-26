import contextlib
import logging
from typing import ContextManager


def is_jupyter() -> bool:
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    shell = get_ipython()
    if shell is None:
        return False
    shell_class_name = type(shell).__name__
    return shell_class_name == "ZMQInteractiveShell"


def run_javascript(js: str) -> None:
    if not is_jupyter():
        raise RuntimeError("Cannot run JS outside of a Jupyter Notebook context")

    from IPython.display import Javascript, display

    display(Javascript(js))


def display_widget() -> None:
    """
    Imported as _ipython_display_ in lmk/jupyter/__init__.py
    to act as a display hook for the module
    """
    try:
        from IPython.display import display
        from lmk.jupyter.widget import get_widget
    except ImportError as err:
        # TODO: improve
        raise RuntimeError(f"Jupyter modules not installed") from err
    widget = get_widget()
    display(widget)


@contextlib.contextmanager
def background_ctx(logger: logging.Logger, ctx: str) -> ContextManager[None]:
    try:
        yield
    except Exception as err:
        logger.exception(f"Error encountered in {ctx}")
