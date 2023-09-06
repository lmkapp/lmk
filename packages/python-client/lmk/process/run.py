import asyncio
import os
import signal

from lmk.process import exc
from lmk.process.attach import attach_simple
from lmk.process.client import wait_for_job
from lmk.process.daemon import ProcessMonitorController, ProcessMonitorDaemon, pid_ctx
from lmk.process.manager import JobManager
from lmk.process.monitor import ProcessMonitor
from lmk.utils.asyncio import asyncio_create_task, async_signal_handler_ctx
from lmk.utils.os import socket_exists


async def run_foreground(
    job_name: str,
    monitor: ProcessMonitor,
    manager: JobManager,
    log_level: str = "INFO",
    attach: bool = True,
) -> None:
    controller = ProcessMonitorController(job_name, monitor, manager)

    with pid_ctx(manager.pid_file(job_name), os.getpid()):
        log_path = manager.log_file(job_name)
        tasks = []
        tasks.append(asyncio_create_task(controller.run(log_path, log_level)))
        if attach:
            tasks.append(asyncio_create_task(attach_simple(job_name, manager)))

        async with async_signal_handler_ctx(
            [signal.SIGINT, signal.SIGTERM],
            lambda signum: controller.send_signal(signum),
        ):
            await asyncio.wait(tasks)


async def run_daemon(
    job_name: str, monitor: ProcessMonitor, manager: JobManager, log_level: str = "INFO"
) -> None:
    process = ProcessMonitorDaemon(job_name, monitor, manager.base_path, log_level)
    process.start()

    socket_path = manager.socket_file(job_name)

    async def wait():
        while not socket_exists(socket_path):
            job = await manager.get_job(job_name)
            if job.ended_at:
                break
            await asyncio.sleep(0.1)

    try:
        await asyncio.wait_for(wait(), 10)
    except asyncio.TimeoutError as err:
        raise Exception("Timed out waiting for monitoring process to come up") from err

    if socket_exists(socket_path):
        await wait_for_job(socket_path, "attach")
        return

    job = await manager.get_job(job_name)
    if job is None:
        raise exc.JobNotFound(job_name)

    raise exc.JobRaisedError(job)
