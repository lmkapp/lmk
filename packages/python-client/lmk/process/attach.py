import asyncio
import io
import json
import logging
import os
import signal
import sys
from typing import Optional

from lmk.process.client import send_signal, wait_for_job
from lmk.utils import wait_for_socket, shutdown_process, socket_exists, input_async


LOGGER = logging.getLogger(__name__)


class ProcessAttachment:
    def __init__(self, process: asyncio.subprocess.Process, job_dir: str):
        self.process = process
        self.job_dir = job_dir
        self.job_id = os.path.split(job_dir)[-1]
        self.socket_path = os.path.join(job_dir, "daemon.sock")
        self.result_path = os.path.join(self.job_dir, "result.json")

    def pause(self) -> None:
        self.process.send_signal(signal.SIGSTOP)

    def resume(self) -> None:
        self.process.send_signal(signal.SIGCONT)

    async def stop(self) -> None:
        await shutdown_process(self.process, 1, 1)

    async def wait(self) -> int:
        if socket_exists(self.socket_path):
            resp = await wait_for_job(self.socket_path)
            exit_code = resp["exit_code"]
        elif os.path.isfile(self.result_path):
            with open(self.result_path) as f:
                result = json.load(f)
                exit_code = result["exit_code"]
        else:
            raise RuntimeError(
                f"Job {self.job_id} exited unexpectedly, unable to retrieve result"
            )

        LOGGER.info("Job %s exited with code %d", self.job_id, exit_code)
        await self.stop()
        return exit_code


async def attach(
    job_dir: str,
    stdout_stream: io.BytesIO = sys.stdout,
    stderr_stream: io.BytesIO = sys.stderr,
) -> ProcessAttachment:
    log_file = os.path.join(job_dir, "output.log")
    socket_path = os.path.join(job_dir, "daemon.sock")

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

    return ProcessAttachment(tail, job_dir)


async def attach_simple(
    job_dir: str,
    stdout_stream: io.BytesIO = sys.stdout,
    stderr_stream: io.BytesIO = sys.stderr,
) -> int:
    attachment = await attach(job_dir, stdout_stream, stderr_stream)
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


async def attach_interactive(job_dir: str) -> Optional[int]:
    socket_path = os.path.join(job_dir, "daemon.sock")

    attachment = await attach(job_dir)

    interupts = 0
    while True:
        task = asyncio.create_task(attachment.wait())
        try:
            return await asyncio.shield(task)
        except (asyncio.CancelledError, KeyboardInterrupt):
            # print("ERROR123")
            # task.cancel()

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
