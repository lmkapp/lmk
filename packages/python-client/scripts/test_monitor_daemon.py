import asyncio
import os
import signal

from lmk.processmon.attach import attach
from lmk.processmon.client import send_signal
from lmk.processmon.child_monitor import ChildMonitor
from lmk.processmon.daemon import ProcessMonitorController, ProcessMonitorDaemon
from lmk.processmon.manager import JobManager
from lmk.utils import setup_logging, shutdown_loop


def get_interrupt_action() -> str:
    while True:
        try:
            input_value = input("interrupt/detach/resume process (i/d/r): ").lower().strip()
            if input_value in {"i", "d", "r"}:
                return input_value
        except KeyboardInterrupt:
            return "d"
        else:
            print(f"Invalid selection: {input_value}")


def main() -> None:
    setup_logging()

    base_path = os.path.expanduser("~/.lmk")
    manager = JobManager(base_path)

    monitor = ChildMonitor(["python", "test.py"])

    job = manager.create_job("python")
    print("JOB ID", job.job_id)
    socket_path = os.path.join(job.job_dir, "daemon.sock")

    controller = ProcessMonitorController(
        -1,
        monitor,
        job.job_dir,
    )
    process = ProcessMonitorDaemon(
        controller,
        job.pid_file
    )
    process.start()

    loop = asyncio.get_event_loop()
    attachment = loop.run_until_complete(attach(job.job_dir))

    interupts = 0
    while True:
        task = loop.create_task(attachment.wait())
        try:
            loop.run_until_complete(task)
            break
        except KeyboardInterrupt:
            task.cancel()

            if interupts > 0:
                loop.run_until_complete(attachment.stop())
                loop.run_until_complete(shutdown_loop(loop))
                break

            attachment.pause()
            action = get_interrupt_action()
            if action == "i":
                attachment.resume()
                loop.run_until_complete(send_signal(socket_path, signal.SIGINT))
                interupts += 1

            if action == "d":
                loop.run_until_complete(attachment.stop())
                loop.run_until_complete(shutdown_loop(loop))
                break
            
            if action == "r":
                attachment.resume()


if __name__ == "__main__":
    main()
