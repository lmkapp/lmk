import abc
from typing import List


class MonitoredProcess(abc.ABC):
    pid: int

    command: List[str]

    @abc.abstractmethod
    async def wait(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def send_signal(self, signum: int) -> None:
        raise NotImplementedError


class ProcessMonitor(abc.ABC):
    """ """

    @abc.abstractmethod
    async def attach(
        self,
        output_path: str,
        log_path: str,
        log_level: str,
    ) -> MonitoredProcess:
        """ """
        raise NotImplementedError
