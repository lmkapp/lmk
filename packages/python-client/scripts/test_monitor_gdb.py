import asyncio
import os
import signal
import sys

from lmk.processmon.attach import attach_simple
from lmk.processmon.daemon import ProcessMonitorController, pid_ctx
from lmk.processmon.gdb import GDBMonitor
from lmk.processmon.manager import JobManager
from lmk.utils import setup_logging, asyncio_create_task, async_signal_handler_ctx


async def main() -> None:
    setup_logging()

    pid = int(sys.argv[1])

    base_path = os.path.expanduser("~/.lmk")
    manager = JobManager(base_path)

    job = manager.create_job("test")
    print("JOB ID", job.job_id)

    monitor = GDBMonitor()

    with pid_ctx(job.pid_file, os.getpid()):
        controller = ProcessMonitorController(
            pid,
            monitor,
            job.job_dir,
        )
        run_task = asyncio_create_task(controller.run())
        attach_task = asyncio_create_task(attach_simple(job.job_dir))

        async with async_signal_handler_ctx(
            [signal.SIGINT, signal.SIGTERM],
            lambda signum: controller.send_signal(signum)
        ):
            await asyncio.wait([run_task, attach_task])


if __name__ == "__main__":
    asyncio.run(main())
