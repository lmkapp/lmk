import asyncio
import getpass
import sys

from lmk.processmon.gdb import gdb_monitor_process


async def main() -> None:
    pid = int(sys.argv[1])
    async with gdb_monitor_process(
        pid,
        f"./stdout-{pid}.txt",
        f"./sterr-{pid}.txt"
    ) as proc:
        print("USER", getpass.getuser())
        print("EXIT CODE", await proc.wait())
        print("STDOUT", await proc.stdout.read())
        print("STDERR", await proc.stderr.read())
    

if __name__ == "__main__":
    asyncio.run(main())
