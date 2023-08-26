import dataclasses as dc
import os
import re
from typing import Optional, Tuple, List

import click


PROJECT_DIR = os.path.dirname(__file__)

SCRIPT_PATH = os.path.join(PROJECT_DIR, "shell_cli.sh")


def get_shell_cli_script(shell: Optional[str] = None) -> str:
    with open(SCRIPT_PATH) as f:
        return f.read()


def detect_shell() -> Optional[str]:
    shell_var = os.getenv("SHELL")
    if shell_var is None:
        return None
    _, name = os.path.split(shell_var)
    return name


def shell_profile_file(shell: Optional[str] = None) -> str:
    if shell is None:
        raise RuntimeError(f"Cannot detect current shell")

    candidates = [f"~/.{shell}rc", f"~/.{shell}_profile"]
    for candidate in candidates:
        fullpath = os.path.expanduser(candidate)
        if os.path.exists(fullpath):
            return candidate

    raise RuntimeError(f"Unable to find shell profile file for shell: {shell}")


SCRIPT_START = "\n# ====== START LMK SHELL PLUGIN ======\n"

SCRIPT_END = "\n# ====== END LMK SHELL PLUGIN ======\n"


def install_script(profile_path: str) -> None:
    profile_path = os.path.expanduser(profile_path)

    with open(profile_path) as f:
        profile = f.read()

    start_index = -1
    try:
        start_index = profile.index(SCRIPT_START)
    except ValueError:
        pass

    end_index = -1
    if start_index != -1:
        try:
            end_index = profile.index(SCRIPT_END, start_index + len(SCRIPT_START))
        except ValueError:
            pass

    if start_index != -1 and end_index != -1:
        new_profile = "".join(
            [
                profile[:start_index],
                SCRIPT_START,
                f". {SCRIPT_PATH}",
                SCRIPT_END,
                profile[end_index + len(SCRIPT_END) :],
            ]
        )
    else:
        new_profile = "".join(
            [
                profile,
                SCRIPT_START,
                f". {SCRIPT_PATH}",
                SCRIPT_END,
            ]
        )

    with open(profile_path, "w+") as f:
        f.write(new_profile)


def uninstall_script(profile_path: str) -> None:
    profile_path = os.path.expanduser(profile_path)

    with open(profile_path) as f:
        profile = f.read()

    start_index = -1
    try:
        start_index = profile.index(SCRIPT_START)
    except ValueError:
        pass

    end_index = -1
    if start_index != -1:
        try:
            end_index = profile.index(SCRIPT_END, start_index + len(SCRIPT_START))
        except ValueError:
            pass

    new_profile = profile
    if start_index != -1 and end_index != -1:
        new_profile = "".join(
            [profile[:start_index], profile[end_index + len(SCRIPT_END) :]]
        )

    if new_profile != profile:
        with open(profile_path, "w+") as f:
            f.write(new_profile)


@dc.dataclass(frozen=True)
class ShellJob:
    command: str
    pid: int
    job_id: int
    state: str


def parse_jobs_output(output: str) -> List[ShellJob]:
    lines = output.strip().split("\n")
    pattern = re.compile(r"\[(\d+)\]\s+[\+\-]?\s+(\d+)\s+(\w+)\s+(.+)$")
    out = []

    for line in lines:
        match = pattern.match(line.strip())
        if not match:
            continue
        job_id = int(match.group(1))
        pid = int(match.group(2))
        state = match.group(3)
        command = match.group(4)
        out.append(ShellJob(command, pid, job_id, state))

    return out


def resolve_pid(pid: str) -> Tuple[int, int]:
    if pid.isdigit():
        return int(pid), None

    if not pid.startswith("%"):
        click.secho(f"Invalid pid: {pid}", fg="red", bold=True)
        raise click.Abort

    job_id = int(pid[1:])

    shell_jobs = os.getenv("SHELL_JOBS")
    if shell_jobs is None:
        click.secho(
            "Cannot use bash job syntax without the shell plugin;"
            "install the shell plugin using `lmk shell-plugin --install`"
        )
        raise click.Abort

    jobs = parse_jobs_output(shell_jobs)
    match = None
    for job in jobs:
        if job.job_id == job_id:
            match = job
            break

    if match is None:
        raise NoShellJobFound(job_id)

    return match.pid, match.job_id


class CannotDetermineShell(click.ClickException):
    """ """

    def __init__(self) -> None:
        super().__init__("Cannot determine shell")
        self.exit_code = 1


class NoShellJobFound(click.ClickException):
    """ """

    def __init__(self, job_id: str) -> None:
        super().__init__(f"No shell job found with ID: {job_id}")
        self.job_id = job_id
        self.exit_code = 1
