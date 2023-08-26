import asyncio
import os
import sys

from lmk.processmon.client import set_notify_on
from lmk.utils import setup_logging


async def main():
    setup_logging()

    job_id = sys.argv[1]
    notify_on = sys.argv[2]

    job_dir = os.path.expanduser(f"~/.lmk/jobs/{job_id}")
    socket_path = os.path.join(job_dir, "daemon.sock")
    await set_notify_on(socket_path, notify_on)


if __name__ == "__main__":
    asyncio.run(main())
