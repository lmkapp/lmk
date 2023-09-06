from typing import Optional, IO

import click

from lmk.exc import LMKError
from lmk.process.models import Job


class JobError(LMKError):
    """
    Base class for errors originating from monitoring command-line jobs
    """


class ProcessNotAttached(JobError):
    """ """

    def __init__(self) -> None:
        super().__init__("Process not attached")


class JobNotFound(JobError, click.ClickException):
    """
    Error indicating a job wasn't found
    """

    exit_code = 1

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Job not found: {name}")

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class JobNotRunning(JobError, click.ClickException):
    """
    Error indicating that a job is not running for a command it needs to be
    """

    exit_code = 1

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Job is not running: {name}")

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class NotLoggedIn(JobError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self) -> None:
        super().__init__("Not logged in. Run `lmk login` to log in to LMK.")

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class LLDBNotFound(JobError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self) -> None:
        super().__init__("`lldb` executable not found.")

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class LLDBCannotAttach(JobError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self) -> None:
        super().__init__(
            "`lldb` is not allowed to attach to processes, which means "
            "you can't monitor alreay-running processes. Try monitoring "
            "your command with the `lmk run` command if possible, or see "
            "https://docs.lmkapp.dev/docs/cli/running-process for information "
            "on how to allow `lldb` to attach to processes."
        )

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class JobRaisedError(JobError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self, job: Job) -> None:
        self.job = job
        super().__init__(
            f"Job {job.name} encountered error: "
            f"{job.error_type or '<unknown>'}: "
            f"{job.error or '<unknown>'}"
        )

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class JobExitedUnexpectedly(JobError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self, job: Job) -> None:
        self.job = job
        super().__init__(
            f"Job {job.name} exited unexpectedly, unable to retrieve exit code"
        )

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class CannotDetermineShell(LMKError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self) -> None:
        super().__init__("Cannot determine shell")
        self.exit_code = 1

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)


class NoShellJobFound(LMKError, click.ClickException):
    """ """

    exit_code = 1

    def __init__(self, job_id: int) -> None:
        super().__init__(f"No shell job found with ID: {job_id}")
        self.job_id = job_id

    def show(self, file: Optional[IO] = None) -> None:
        click.secho(str(self), fg="red", file=file)
