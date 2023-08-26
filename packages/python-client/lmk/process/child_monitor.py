import asyncio
import logging
import os
import pty
import shlex
from typing import List

from lmk.process.monitor import ProcessMonitor, MonitoredProcess
from lmk.utils import wait_for_fd


LOGGER = logging.getLogger(__name__)


class MonitoredChildProcess(MonitoredProcess):
    def __init__(
        self,
        process: asyncio.subprocess.Process,
        command: List[str],
        output_fd: int,
        output_path: str,
    ) -> None:
        self.process = process
        self.command = command
        self.output_fd = output_fd
        self.output_path = output_path

    @property
    def pid(self) -> int:
        return self.process.pid

    async def send_signal(self, signum: int) -> None:
        self.process.send_signal(signum)

    async def wait(self) -> int:
        output_ready = asyncio.create_task(wait_for_fd(self.output_fd))
        wait = asyncio.create_task(self.process.wait())

        with open(self.output_path, "ab+", buffering=0) as output_file:
            while not wait.done():
                await asyncio.wait(
                    [output_ready, wait], return_when=asyncio.FIRST_COMPLETED
                )

                if output_ready.done():
                    output = os.read(self.output_fd, 1000)
                    output_file.write(output)
                    output_ready = asyncio.create_task(wait_for_fd(self.output_fd))

            output_ready.cancel()

            return wait.result()


class ChildMonitor(ProcessMonitor):
    """ """

    def __init__(self, argv: List[str]) -> None:
        if len(argv) < 1:
            raise ValueError("argv must have length >=1")
        self.argv = argv

    async def attach(
        self,
        pid: int,
        output_path: str,
        log_path: str,
        log_level: str,
    ) -> MonitoredChildProcess:
        read_output, write_output = pty.openpty()

        proc = await asyncio.create_subprocess_exec(
            *self.argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=write_output,
            stderr=write_output,
            bufsize=0,
            start_new_session=True,
        )
        LOGGER.debug(
            "Created child process: [%s], pid: %d", shlex.join(self.argv), proc.pid
        )
        return MonitoredChildProcess(proc, self.argv, read_output, output_path)
