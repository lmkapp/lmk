import asyncio
import os
import sys

from lmk.processmon.attach import attach_simple
from lmk.utils import setup_logging


async def main():
    setup_logging()
    job_id = sys.argv[1]
    job_dir = os.path.expanduser(f"~/.lmk/jobs/{job_id}")
    await attach_simple(job_dir)


if __name__ == "__main__":
    asyncio.run(main())
