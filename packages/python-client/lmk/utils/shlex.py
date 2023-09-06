import shlex
from typing import List


def shlex_join(args: List[str]) -> str:
    # This is only available in python 3.8+
    if hasattr(shlex, "join"):
        return shlex.join(args)

    return " ".join(shlex.quote(arg) for arg in args)
