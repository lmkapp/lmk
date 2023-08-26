import asyncio
import os
import signal

from lmk.processmon.attach import attach_simple
from lmk.processmon.child_monitor import ChildMonitor
from lmk.processmon.daemon import ProcessMonitorController, pid_ctx
from lmk.processmon.manager import JobManager
from lmk.utils import async_signal_handler_ctx, asyncio_create_task, setup_logging


async def main() -> None:
    setup_logging()

    base_path = os.path.expanduser("~/.lmk")
    manager = JobManager(base_path)

    monitor = ChildMonitor(["python", "test.py"])

    job = manager.create_job("python")
    print("JOB ID", job.job_id)

    with pid_ctx(job.pid_file, os.getpid()):
        controller = ProcessMonitorController(
            -1,
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
