import asyncio
import json
import os
import signal

from lmk.process.attach import attach_simple
from lmk.process.client import wait_for_job
from lmk.process.daemon import ProcessMonitorController, ProcessMonitorDaemon, pid_ctx
from lmk.process.manager import NewJob
from lmk.utils.asyncio import asyncio_create_task, async_signal_handler_ctx
from lmk.utils.os import socket_exists


async def run_foreground(
    job: NewJob,
    controller: ProcessMonitorController,
    log_level: str = "INFO",
    attach: bool = True,
) -> None:
    with pid_ctx(job.pid_file, os.getpid()):
        log_path = os.path.join(job.job_dir, "lmk.log")
        tasks = []
        tasks.append(asyncio_create_task(controller.run(log_path, log_level)))
        if attach:
            tasks.append(asyncio_create_task(attach_simple(job.job_dir)))

        async with async_signal_handler_ctx(
            [signal.SIGINT, signal.SIGTERM],
            lambda signum: controller.send_signal(signum),
        ):
            await asyncio.wait(tasks)


async def run_daemon(
    job: NewJob, controller: ProcessMonitorController, log_level: str = "INFO"
) -> None:
    process = ProcessMonitorDaemon(controller, job.pid_file, log_level)
    process.start()

    socket_path = os.path.join(job.job_dir, "daemon.sock")
    result_path = os.path.join(job.job_dir, "result.json")

    try:
        async with asyncio.timeout(10):
            while not socket_exists(socket_path) and not os.path.exists(result_path):
                await asyncio.sleep(0.1)
    except asyncio.TimeoutError as err:
        raise Exception("Timed out waiting for monitoring process to come up") from err

    if socket_exists(socket_path):
        await wait_for_job(socket_path, "attach")
        return

    with open(result_path) as f:
        result = json.load(f)
        raise Exception(f"{result['error_type']}: {result['error']}")
