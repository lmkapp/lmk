import asyncio
import os

from lmk.processmon.manager import JobManager


def pad(value: str, length: int, character: str = " ") -> str:
    if len(value) > length:
        return value[:length - 3] + "..."
    return value + character * (length - len(value))


async def main():
    base_path = os.path.expanduser("~/.lmk")
    manager = JobManager(base_path)
    print(
        pad("id", 30),
        pad("pid", 10),
        pad("status", 12),
        pad("notify", 10),
        pad("started", 30),
    )
    # job_ids = manager.get_all_job_ids()
    # async for job in manager.get_jobs(job_ids):
    async for job in manager.list_running_jobs():
        print(
            pad(str(job.job_id), 30),
            pad(str(job.target_pid), 10),
            pad("running    " if job.running else "not-running", 12),
            pad(job.notify_on, 10),
            pad(job.started_at.isoformat(), 30),
        )


if __name__ == "__main__":
    asyncio.run(main())
