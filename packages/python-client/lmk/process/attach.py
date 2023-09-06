import asyncio
import io
import logging
import signal
import sys
from typing import Optional, IO

from lmk.process import exc
from lmk.process.client import send_signal, wait_for_job
from lmk.process.manager import JobManager
from lmk.utils import wait_for_socket, shutdown_process, socket_exists, input_async


LOGGER = logging.getLogger(__name__)


class ProcessAttachment:
    def __init__(
        self, process: asyncio.subprocess.Process, job_name: str, manager: JobManager
    ):
        self.process = process
        self.job_name = job_name
        self.manager = manager

    def pause(self) -> None:
        self.process.send_signal(signal.SIGSTOP)

    def resume(self) -> None:
        self.process.send_signal(signal.SIGCONT)

    async def stop(self) -> None:
        await shutdown_process(self.process, 1, 1)

    async def wait(self) -> int:
        socket_path = self.manager.socket_file(self.job_name)
        if socket_exists(socket_path):
            resp = await wait_for_job(socket_path)
            exit_code = resp["exit_code"]
        else:
            job = await self.manager.get_job(self.job_name)
            if job is None:
                raise exc.JobNotFound(self.job_name)

            exit_code = job.exit_code
            if exit_code is None:
                raise exc.JobExitedUnexpectedly(job)

        LOGGER.info("Job %s exited with code %d", self.job_name, exit_code)
        await self.stop()
        return exit_code


async def attach(
    job_name: str,
    manager: JobManager,
    stdout_stream: IO[str] = sys.stdout,
    stderr_stream: IO[str] = sys.stderr,
) -> ProcessAttachment:
    log_file = manager.output_file(job_name)
    socket_path = manager.socket_file(job_name)

    await wait_for_socket(socket_path, 3)

    tail = await asyncio.create_subprocess_exec(
        "tail",
        "-f",
        log_file,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=stdout_stream,
        stderr=stderr_stream,
        bufsize=0,
        start_new_session=True,
    )

    return ProcessAttachment(tail, job_name, manager)


async def attach_simple(
    job_name: str,
    manager: JobManager,
    stdout_stream: IO[str] = sys.stdout,
    stderr_stream: IO[str] = sys.stderr,
) -> int:
    attachment = await attach(job_name, manager, stdout_stream, stderr_stream)
    try:
        return await attachment.wait()
    except:
        await attachment.stop()
        raise


async def get_interrupt_action() -> str:
    while True:
        try:
            input_value = await input_async("interrupt/detach/resume process (i/d/r): ")
            input_value = input_value.lower().strip()
            if input_value in {"i", "d", "r"}:
                return input_value
        except KeyboardInterrupt:
            return "d"
        else:
            print(f"Invalid selection: {input_value}")


async def attach_interactive(job_name: str, manager: JobManager) -> Optional[int]:
    socket_path = manager.socket_file(job_name)

    attachment = await attach(job_name, manager)

    interupts = 0
    while True:
        task = asyncio.create_task(attachment.wait())
        try:
            return await asyncio.shield(task)
        except (asyncio.CancelledError, KeyboardInterrupt):
            if interupts > 0:
                task.cancel()
                await attachment.stop()
                break

            attachment.pause()

            action_task = asyncio.create_task(get_interrupt_action())

            await asyncio.wait([action_task, task], return_when=asyncio.FIRST_COMPLETED)

            if task.done():
                return task.result()

            task.cancel()

            action = action_task.result()
            if action == "i":
                attachment.resume()
                await send_signal(socket_path, signal.SIGINT)
                interupts += 1

            if action == "d":
                await attachment.stop()
                break

            if action == "r":
                attachment.resume()

    return None
