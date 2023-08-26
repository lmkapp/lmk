import lmk.patches

lmk.patches.patch()

from lmk import jupyter, methods
from lmk.instance import get_instance, set_instance
from lmk.jupyter import (
    _jupyter_labextension_paths,
    _jupyter_nbextension_paths,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "jupyter",
    "get_instance",
    "set_instance",
    "_jupyter_labextension_paths",
    "_jupyter_nbextension_paths",
]
__all__ += methods.__all__


def __getattr__(name: str):
    if name in globals():
        return globals()[name]
    if name in methods.__all__:
        return getattr(methods, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
