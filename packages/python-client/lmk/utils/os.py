import contextlib
import io
import logging
import os
import signal
import stat
from typing import Callable, ContextManager, List, Optional


LOGGER = logging.getLogger(__name__)


def socket_exists(path: str) -> bool:
    try:
        mode = os.stat(path).st_mode
    except FileNotFoundError:
        return False
    return stat.S_ISSOCK(mode)


@contextlib.contextmanager
def signal_handler_ctx(
    signals: List[int],
    handler: Callable[[int], None],
) -> ContextManager[None]:
    def handle_signal(signum, _):
        handler(signum)

    prev_handlers = {}
    for signal_num in signals:
        prev_handlers[signal_num] = signal.signal(signal_num, handle_signal)

    try:
        yield
    finally:
        for signal_num, old_handler in prev_handlers.items():
            signal.signal(signal_num, old_handler)


def read_last_lines(
    path: str, num_lines: int, max_size: Optional[int] = None
) -> List[str]:
    size = os.path.getsize(path)

    with open(path) as file:
        seek_start = max(size - max_size, 0)
        if seek_start > 0:
            file.seek(seek_start)
        lines = []
        for line in file:
            lines.append(line)
            if len(lines) > num_lines:
                lines.pop(0)

        return lines
