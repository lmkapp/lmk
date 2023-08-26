import asyncio
import os
import sys

from lmk.processmon.client import send_signal
from lmk.utils import setup_logging


async def main():
    setup_logging()

    job_id = sys.argv[1]
    signal = sys.argv[2]
    if signal.isdigit():
        signal = int(signal)

    job_dir = os.path.expanduser(f"~/.lmk/jobs/{job_id}")
    socket_path = os.path.join(job_dir, "daemon.sock")
    await send_signal(socket_path, signal)


if __name__ == "__main__":
    asyncio.run(main())
