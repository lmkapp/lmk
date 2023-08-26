import asyncio
import contextlib
import inspect
import logging
import signal
import sys
import time
from functools import partial, wraps
from typing import Optional, Awaitable, Any, AsyncContextManager, List, Callable

from lmk.utils.os import socket_exists


LOGGER = logging.getLogger(__name__)


async def shutdown_loop(
    loop: asyncio.AbstractEventLoop,
    timeout: Optional[float] = None,
    cancel_running: bool = True,
) -> bool:
    current_task = asyncio.current_task()
    tasks = [task for task in asyncio.all_tasks(loop) if task is not current_task]

    if not tasks:
        return True

    if cancel_running:
        for task in tasks:
            task.cancel()

    all_done_coro = asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    if timeout is None:
        await all_done_coro
        return True

    try:
        await asyncio.wait_for(all_done_coro, timeout)
    except TimeoutError:
        return False

    return True


@contextlib.contextmanager
def loop_ctx(loop: asyncio.AbstractEventLoop):
    try:
        yield
    finally:
        loop.run_until_complete(shutdown_loop(loop))
        loop.close()


async def shutdown_process(
    process: asyncio.subprocess.Process,
    soft_timeout: Optional[float] = None,
    hard_timeout: Optional[float] = None,
) -> int:
    """ """
    start = time.time()

    wait = asyncio.shield(process.wait())
    # Check if the process is already finished first
    try:
        return await asyncio.wait_for(wait, 0)
    except asyncio.TimeoutError:
        pass

    process.send_signal(signal.SIGINT)
    try:
        return await asyncio.wait_for(wait, soft_timeout)
    except (TimeoutError, asyncio.CancelledError):
        pass

    after_soft_timeout = time.time()
    hard_timeout_left = None
    if hard_timeout is not None:
        hard_timeout_left = hard_timeout - (after_soft_timeout - start)

    if hard_timeout_left is None or hard_timeout_left > 0:
        process.terminate()
        try:
            return await asyncio.wait_for(wait, hard_timeout_left)
        except (TimeoutError, asyncio.CancelledError):
            pass

    process.kill()


def asyncio_create_task(
    coro: Awaitable[Any],
    loop: Optional[asyncio.AbstractEventLoop] = None,
    logger: logging.Logger = LOGGER,
) -> asyncio.Task:
    create = asyncio.create_task
    if loop is not None:
        create = loop.create_task

    async def wrapped():
        try:
            await coro
        except Exception:
            logger.exception("Error in %s", coro)

    return create(wrapped())


@contextlib.asynccontextmanager
async def async_signal_handler_ctx(
    signals: List[Any],
    handler: Callable[[int], Awaitable[None]],
) -> AsyncContextManager[None]:
    loop = asyncio.get_running_loop()

    tasks = []

    def handle_signal(signum):
        tasks.append(asyncio_create_task(handler(signum), loop))

    for sig in signals:
        loop.add_signal_handler(sig, partial(handle_signal, sig))

    try:
        yield
    finally:
        for sig in signals:
            loop.remove_signal_handler(sig)
        if tasks:
            await asyncio.wait(tasks)


async def wait_for_socket(
    socket_path: str,
    timeout: Optional[float] = None,
    poll_interval: float = 0.1,
) -> None:
    start = time.time()

    while not socket_exists(socket_path) and (
        timeout is None or time.time() - start < timeout
    ):
        await asyncio.sleep(poll_interval)

    if not socket_exists(socket_path):
        raise TimeoutError


async def wait_for_fd(fd: int) -> None:
    loop = asyncio.get_running_loop()
    future = asyncio.Future()
    loop.add_reader(fd, future.set_result, None)
    future.add_done_callback(lambda f: loop.remove_reader(fd))
    await future


async def input_async(prompt: str) -> str:
    print(prompt, end="")
    sys.stdout.flush()
    await wait_for_fd(sys.stdin.fileno())
    return sys.stdin.readline()


async def check_output(args: List[str]) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    exit_code = await proc.wait()
    if exit_code == 0:
        return stdout.decode()

    raise CalledProcessError(args, stdout.decode(), stderr.decode(), exit_code)


class CalledProcessError(Exception):
    def __init__(
        self, args: List[str], stdout: str, stderr: str, exit_code: int
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        super().__init__(
            f"Command {args} exited with status {exit_code}.\n"
            f"Stdout:\n{stdout}\n\n"
            f"Stderr:\n{stderr}"
        )


def exponential_backoff(
    failures: int, base: float = 0.5, exponent: float = 2.0
) -> float:
    return base * failures**exponent


def simple_retry_rule(
    max_attempts: Optional[int] = 4,
    backoff: Callable[[int], float] = exponential_backoff,
):
    def rule(failures: int, error: Exception):
        if max_attempts is not None and failures >= max_attempts:
            return None
        return backoff(failures)

    return rule


RetryRule = Callable[[int, Exception], Optional[float]]


def async_retry(func: Optional[Callable] = None, *, rule: Optional[RetryRule] = None):
    if rule is None:
        rule = simple_retry_rule()

    def dec(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            failures = 0
            while True:
                try:
                    return await f(*args, **kwargs)
                except Exception as err:
                    LOGGER.debug("Error in async_retry", exc_info=True)
                    failures += 1
                    sleep_for = rule(failures, err)
                    if sleep_for is None:
                        raise
                    await asyncio.sleep(sleep_for)

        return wrapper

    if func is None:
        return dec

    return dec(func)


def async_callback(
    func: Optional[Callable[[], Any]] = None,
    *,
    loop: Optional[asyncio.AbstractEventLoop] = None,
):
    def dec(f):
        def done_cb(future):
            try:
                future.result()
            except Exception:
                LOGGER.exception(
                    "%s handler: %s raised exception", signal, getattr(f, "__name__", f)
                )

        @wraps(f)
        def handler(*args, **kwargs):
            use_loop = loop
            if use_loop is None:
                use_loop = asyncio.get_event_loop()

            result = f(*args, **kwargs)
            if inspect.isawaitable(result):
                task = use_loop.create_task(result)
                task.add_done_callback(done_cb)
                return task

            return result

        return handler

    if func is None:
        return dec

    return dec(func)
