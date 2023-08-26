import asyncio
import atexit
import logging
from concurrent.futures import ThreadPoolExecutor, Executor, Future
from typing import Optional

from lmk.constants import API_URL
from lmk.generated.api_client import ApiClient as DefaultApiClient, Configuration


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

    def apply_async(self, func, args) -> Future:
        return asyncio.wrap_future(self.executor.submit(func, *args))

    def close(self) -> None:
        self.executor.shutdown(wait=True)

    def join(self) -> None:
        pass


class ApiClient(DefaultApiClient):
    """
    ApiClient subclass that uses a ThreadPoolExecutor wrapped with _ExecutorWrapper
    rather than a ThreadPool from multiprocessing
    """

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
