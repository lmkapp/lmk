from typing import Optional, Any

from IPython import get_ipython
from IPython.core.magic import Magics, line_cell_magic, magics_class, line_magic

from lmk import exc
from lmk.instance import get_instance
from lmk.jupyter.utils import display_widget
from lmk.jupyter.widget import get_widget


@magics_class
class LMKMagics(Magics):
    @line_magic
    def lmk_widget(self, line, cell=None):
        display_widget()

    @line_cell_magic
    def lmk(self, line, cell=None):
        instance = get_instance()
        if not instance.logged_in():
            raise exc.NotLoggedIn()

        args = {"state": "stop", "immediate": bool(cell)}
        tokens = list(map(str.lower, line.strip().split()))
        for token in tokens:
            if token == "immediate":
                args["immediate"] = True
                continue
            if "=" not in token:
                raise ValueError(f"Malformed option: '{token}'")
            key, value = map(str.strip, token.split("=", 1))
            if key == "on":
                if value not in {"none", "stop", "error"}:
                    raise ValueError(f"Invalid option for 'on': '{value}'")
                args["state"] = value
                continue
            if key == "immediate":
                if value not in {"true", "false", "1", "0"}:
                    raise ValueError(f"Invalid option for 'immediate': '{value}'")
                bool_value = value in {"true", "1"}
                args["immediate"] = bool_value
                continue

            raise ValueError(f"Invalid option: '{token}'")

        widget = get_widget()
        widget.set_monitoring_state(**args)

        if cell:
            exec(cell, None, self.shell.user_ns)


def register_magics(
    shell: Optional[Any] = None,
    raise_on_no_shell: bool = True,
) -> bool:
    if shell is None:
        shell = get_ipython()
    if shell is None and raise_on_no_shell:
        raise RuntimeError("Not in an IPython shell")
    if shell is not None:
        shell.register_magics(LMKMagics)
        return True
    return False
