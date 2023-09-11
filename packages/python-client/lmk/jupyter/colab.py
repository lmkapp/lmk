import os
import warnings

from lmk.jupyter.widget import get_widget


def is_google_colab() -> bool:
    """
    Check if the current context appears to be within a colab notebook
    """
    return bool(os.getenv("COLAB_RELEASE_TAG"))


def enable_google_colab_support(check_if_colab: bool = True) -> None:
    """
    Enable Google Colab support. By default only tries to do this if we
    detect we're running in a colab notebook.
    """
    if check_if_colab and not is_google_colab():
        return

    try:
        from google.colab import output
    except ImportError as err:
        warnings.warn(
            "Unable to import the `google.colab.output` module, google colab support is not enabled.",
            RuntimeWarning,
        )
        return

    def widget_update():
        get_widget().send_state()

    output.register_callback("lmk.widget.sync", widget_update)
    output.enable_custom_widget_manager()
