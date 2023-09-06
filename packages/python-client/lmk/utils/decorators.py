from typing import Callable, Tuple, Any


def stack_decorators(
    *decs: Callable[..., Any]
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def dec(f):
        for func in reversed(decs):
            f = func(f)
        return f

    return dec
