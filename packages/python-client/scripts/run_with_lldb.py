import json
import os
import sys
import subprocess
import sys
from typing import List


def main(argv: List[str]) -> int:
    info_str = subprocess.check_output([
        "lldb",
        "--print-script-interpreter-info"
    ])
    info = json.loads(info_str)

    pythonpath_components = [
        info["lldb-pythonpath"]
    ]
    if os.getenv("PYTHONPATH"):
        pythonpath_components.append(os.getenv("PYTHONPATH"))
    
    pythonpath = ":".join(pythonpath_components)

    process = subprocess.Popen(
        [info["executable"]] + argv,
        env={
            **os.environ,
            "PYTHONPATH": pythonpath
        }
    )
    return process.wait()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
