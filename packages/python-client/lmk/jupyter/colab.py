import asyncio
import os
import logging
import warnings
from typing import TYPE_CHECKING

from blinker import signal

from lmk.jupyter.notebook_info import find_server_and_session
from lmk.jupyter.utils import background_ctx
from lmk.utils.blinker import wait_for_signal

if TYPE_CHECKING:
    from lmk.jupyter.widget import LMKWidget


colab_support_enabled_changed = signal("colab-support-enabled-changed")


LOGGER = logging.getLogger(__name__)

COLAB_SUPPORT_ENABLED = False

CALLBACK_REGISTERED = False


def is_google_colab() -> bool:
    """
    Check if the current context appears to be within a colab notebook
    """
    return bool(os.getenv("COLAB_RELEASE_TAG"))


def colab_support_enabled() -> bool:
    """
    Determine if colab support is currently enabled. If in a colab
    environment it will be enabled by default
    """
    return COLAB_SUPPORT_ENABLED


def enable_google_colab_support(check_if_colab: bool = True) -> None:
    """
    Enable Google Colab support. By default only tries to do this if we
    detect we're running in a colab notebook.
    """
    global COLAB_SUPPORT_ENABLED, CALLBACK_REGISTERED

    from lmk.jupyter.widget import get_widget

    if COLAB_SUPPORT_ENABLED:
        return

    if check_if_colab and not is_google_colab():
        return

    try:
        from google.colab import output
    except ImportError:
        warnings.warn(
            "Unable to import the `google.colab.output` module, google colab support is not enabled.",
            RuntimeWarning,
        )
        return

    def widget_update():
        with background_ctx(LOGGER, "colab.enable_google_colab_support"):
            LOGGER.debug("Sending widget state for colab support")
            get_widget().send_state()

    if not CALLBACK_REGISTERED:
        output.register_callback("lmk.widget.sync", widget_update)
        CALLBACK_REGISTERED = True

    output.enable_custom_widget_manager()

    COLAB_SUPPORT_ENABLED = True
    colab_support_enabled_changed.send(None, old_value=False, new_value=True)


def disable_google_colab_support() -> None:
    """ """
    global COLAB_SUPPORT_ENABLED

    if not COLAB_SUPPORT_ENABLED:
        return

    from google.colab import output

    output.disable_custom_widget_manager()

    COLAB_SUPPORT_ENABLED = False
    colab_support_enabled_changed.send(None, old_value=True, new_value=False)


async def observe_google_colab_url(widget: "LMKWidget") -> None:
    """ """

    def get_url(file_id):
        return f"https://colab.research.google.com/drive/{file_id}"

    loop = asyncio.get_running_loop()

    file_id = None
    while True:
        if not colab_support_enabled():
            await wait_for_signal(colab_support_enabled_changed)
            continue

        try:
            _, session = await loop.run_in_executor(None, find_server_and_session)
        except Exception:
            LOGGER.exception("Error getting session")
        else:
            if session is None:
                LOGGER.error("Unable to get session")
            else:
                new_file_id = session["path"].split("=", 1)[1]
                if new_file_id and new_file_id != file_id:
                    file_id = new_file_id
                    url = get_url(file_id)
                    if url != widget.url:
                        widget.url = url
        finally:
            await asyncio.sleep(60)
