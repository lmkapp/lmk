from typing import Callable, Tuple


def stack_decorators(
    *decs: Tuple[Callable[[Callable[[], None]], Callable[[], None]], ...]
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def dec(f):
        for func in reversed(decs):
            f = func(f)
        return f

    return dec
