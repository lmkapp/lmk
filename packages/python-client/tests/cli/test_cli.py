import os
import re
import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["lmk", "lmk.shell_cli"])
def test_cli_help_simple(module) -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", module, "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        env={**os.environ, "PYDEVD_DISABLE_FILE_VALIDATION": "1"},
    )
    stdout, stderr = process.communicate()

    assert not stderr
    assert stdout.startswith("Usage:")
    assert process.wait() == 0


@pytest.mark.parametrize("exit_code", [0, 1])
def test_cli_run(exit_code: int) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lmk",
            "run",
            f"python -c 'import sys, time; time.sleep(3); print(\"done\"); sys.exit({exit_code})'",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        env={**os.environ, "PYDEVD_DISABLE_FILE_VALIDATION": "1"},
    )
    stdout, stderr = process.communicate()

    assert not stderr
    lines = stdout.strip().split("\n")

    assert len(lines) == 2
    assert re.match(r"^Job ID: python-\d+-[a-z0-9]+$", lines[0])
    assert lines[1] == "done"
    assert process.wait() == exit_code
