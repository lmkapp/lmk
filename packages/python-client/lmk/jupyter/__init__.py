from lmk.jupyter.utils import (
    is_jupyter,
    run_javascript,
    display_widget as _ipython_display_,
)
from lmk.jupyter.hooks import _jupyter_labextension_paths, _jupyter_nbextension_paths

__all__ = [
    "is_jupyter",
    "run_javascript",
    "_ipython_display_",
    "_jupyter_labextension_paths",
    "_jupyter_nbextension_paths",
]

try:
    from lmk.jupyter.widget import get_widget, set_widget, IPythonMonitoringState
except ImportError:
    pass
else:
    from lmk.jupyter import methods
    from lmk.jupyter.magics import register_magics

    __all__ += ["get_widget", "set_widget", "IPythonMonitoringState"]
    __all__ += methods.__all__

    def __getattr__(name: str):
        if name in globals():
            return globals()[name]
        if name in methods.__all__:
            return getattr(methods, name)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    register_magics(raise_on_no_shell=False)
