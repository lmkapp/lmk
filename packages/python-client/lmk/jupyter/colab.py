import os
import logging
import warnings

from lmk.jupyter.utils import background_ctx


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


def disable_google_colab_support() -> None:
    """ """
    global COLAB_SUPPORT_ENABLED

    if not COLAB_SUPPORT_ENABLED:
        return

    from google.colab import output

    output.disable_custom_widget_manager()

    COLAB_SUPPORT_ENABLED = False
