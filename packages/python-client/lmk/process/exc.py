from typing import Optional, IO

import click

from lmk.exc import LMKError


class JobError(LMKError):
    """
    Base class for errors originating from monitoring command-line jobs
    """


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
