import asyncio
from typing import Any

import blinker


def wait_for_signal(
    signal: blinker.Signal, sender: Any = blinker.ANY
) -> asyncio.Future:
    future = asyncio.Future()

    def handle_signal(sender, **kwargs):
        future.set_result((sender, kwargs))
        signal.disconnect(handle_signal, sender)

    signal.connect(handle_signal, sender)

    return future
