import asyncio
import atexit
import logging
import time
from concurrent.futures import ThreadPoolExecutor, Executor
from functools import wraps
from typing import Optional, Callable

from lmk.constants import API_URL
from lmk.generated.api_client import ApiClient as DefaultApiClient, Configuration
from lmk.generated.exceptions import ApiException


LOGGER = logging.getLogger(__name__)


class _ExecutorWrapper:
    """
    Wrap an executor to have the same API (at least the parts that the generated API
    client uses) as multiprocessing.pool.ThreadPool -- this is so that rather than
    an ApplyResult it returns a Future that can be wrapped as a coroutine and used with
    asyncio
    """

    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def apply_async(self, func, args) -> asyncio.Future:
        return asyncio.wrap_future(self.executor.submit(func, *args))

    def close(self) -> None:
        self.executor.shutdown(wait=True)

    def join(self) -> None:
        pass


def retry(
    func: Optional[Callable] = None,
    retry_in: Optional[Callable[[Exception, int], Optional[float]]] = None,
):
    if retry_in is None:

        def retry_in(error, attempt):
            return None

    def dec(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                attempt += 1
                try:
                    return f(*args, **kwargs)
                except Exception as error:
                    retry_ivl = retry_in(error, attempt)

                    if retry_ivl is None:
                        raise

                    LOGGER.debug(
                        "Retrying %s in %.2fs", f.__name__, retry_ivl, exc_info=True
                    )
                    time.sleep(retry_ivl)

        return wrapper

    if func is None:
        return dec

    return dec(func)


def api_client_retry_in(error: Exception, attempt: int) -> Optional[float]:
    if not isinstance(error, ApiException):
        return None

    if error.status == 429:
        return min(10.0, 0.5 * 2**attempt)

    return None


class ApiClient(DefaultApiClient):
    """
    ApiClient subclass that uses a ThreadPoolExecutor wrapped with _ExecutorWrapper
    rather than a ThreadPool from multiprocessing
    """

    @retry(retry_in=api_client_retry_in)
    def request(self, *args, **kwargs):
        return super().request(*args, **kwargs)

    @property
    def pool(self):
        if self._pool is None:
            atexit.register(self.close)
            self._pool = _ExecutorWrapper(ThreadPoolExecutor(self.pool_threads))
        return self._pool


def api_client(
    server_url: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> ApiClient:
    """
    Create an API client instance
    """
    if server_url is None:
        server_url = API_URL
    if logger is None:
        logger = LOGGER

    config = Configuration(host=server_url)
    config.logger = {key: logger for key in config.logger}

    return ApiClient(config)
