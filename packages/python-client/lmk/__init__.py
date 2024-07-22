import lmk.patches

lmk.patches.patch()

from lmk import jupyter, methods  # noqa: E402
from lmk.constants import VERSION as __version__  # noqa: E402
from lmk.instance import get_instance, set_instance  # noqa: E402
from lmk.jupyter import (  # noqa: E402
    _jupyter_labextension_paths,
    _jupyter_nbextension_paths,
)

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
