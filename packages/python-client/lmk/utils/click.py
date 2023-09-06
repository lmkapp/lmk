import asyncio
from functools import wraps
from typing import Optional, Callable, Any

import click


def async_group(func: Optional[Callable] = None, **kws) -> click.Group:
    def dec(f):
        @click.group(**kws)
        @wraps(f)
        def wrapper(*args, **kwargs):
            return asyncio.run(f(*args, **kwargs))

        return wrapper

    if func is not None:
        return dec(func)

    return dec  # type: ignore


def async_command(
    group: click.Group, **kws
) -> Callable[[Callable[..., Any]], click.Command]:
    def dec(f):
        @group.command(**kws)
        @wraps(f)
        def wrapper(*args, **kwargs):
            return asyncio.run(f(*args, **kwargs))

        return wrapper

    return dec
