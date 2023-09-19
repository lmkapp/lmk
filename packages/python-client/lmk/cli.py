import click
import os
import psutil
import shlex
import signal as signal_module
import sys
import textwrap
from typing import List, Optional, Dict, Any

from lmk.instance import get_instance, set_instance, Instance
from lmk.process import exc
from lmk.process.attach import attach_interactive
from lmk.process.child_monitor import ChildMonitor
from lmk.process.client import send_signal, update_job
from lmk.process.lldb_monitor import LLDBProcessMonitor, check_lldb
from lmk.process.manager import JobManager
from lmk.process.run import run_foreground, run_daemon
from lmk.process.shell_plugin import (
    detect_shell,
    install_script,
    uninstall_script,
    shell_profile_file,
    resolve_pid,
    get_shell_cli_script,
)
from lmk.utils.click import async_command, async_group
from lmk.utils.decorators import stack_decorators
from lmk.utils.logging import setup_logging


# Sigh, just to make the vercel build work; sqlite3
# docs not exist there, so the cli() setup fails. Side
# note though--is that the wrong place to be doing that setup
# if it runs _even on a --help command???_
DOCS_ONLY = bool(os.getenv("LMK_CLI_DOCS_ONLY"))


def _check_login() -> None:
    instance = get_instance()
    if instance.logged_in():
        return

    resp = click.confirm("You are not logged in; would you like to log in now?")
    if not resp:
        raise exc.NotLoggedIn()

    instance.login(force=True)


cli_args = stack_decorators(
    click.option(
        "-l", "--log-level", default="WARN", help="Log level, defaults to WARN"
    ),
    click.option(
        "-b",
        "--base-path",
        default=os.path.expanduser("~/.lmk"),
        help="Path to the LMK configuration directory; defaults to ~/.lmk",
    ),
)


@async_group(
    help=(
        "The LMK Command Line Interface. This allows you to monitor command-line processes remotely "
        "via the LMK web app."
    )
)
@cli_args
@click.pass_context
async def cli(ctx: click.Context, log_level: str, base_path: str):
    if DOCS_ONLY:
        return
    
    setup_logging(level=log_level)
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level

    manager = JobManager(base_path)
    await manager.setup()

    ctx.obj["manager"] = manager

    config_path = os.path.join(base_path, "config")
    set_instance(Instance(config_path=config_path))


@cli.command(
    help=(
        "Authenticate with the LMK API. This should typically be the first command you run when "
        "using the CLI for the first time, and it allows you to use the other commands."
    )
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help=(
        "By default, this will be a no-op if you are already logged in. Pass --force to "
        "force the CLI to re-authenticate with LMK."
    ),
)
@click.option(
    "-m",
    "--manual",
    is_flag=True,
    default=False,
    help="Print the authentication URL instead of attempting to open the page in a web browser.",
)
def login(force, manual):
    instance = get_instance()
    instance.login(force=force, auth_mode="manual" if manual else None)


attach_option = click.option(
    "--attach/--no-attach",
    default=True,
    help=(
        "Attach to the process, meaning you will see the logs from the process appearing in your "
        "console in real time. You can detach at any time, at which point you can choose to let the "
        "process keep running or interrupt it. After detaching, you will also be able to re-attach at any "
        "time while the process is running."
    ),
)

name_option = click.option(
    "-N",
    "--name",
    default=None,
    help=(
        "Job name for the job you want to run. This will be visible in the LMK dashboard, "
        "and it can be passed to other commands that take a job ID such as `attach`, `kill`, etc. "
        "If not passed, a name will be generated."
    ),
)


def notify_on_option(default: str = "none"):
    return click.option(
        "-n",
        "--notify",
        default=default,
        type=click.Choice(["stop", "error", "none"]),
        help=(
            "Set the initial `notify_on` value for the process. If `stop`, you will get a notification "
            "whenever the process completes for any reason. If `error`, you will only get a notification "
            "if it exists with a non-zero status code. If `none`, you will note be notified at all, but will "
            "still be able to monitor the process of the script via the LMK web app. This can be changed after "
            "launching the process initially, so if you omit it initially you can always choose to notify yourself "
            "later."
        ),
    )


@async_command(
    cli,
    short_help="Run a command line process, and monitor it using LMK",
    help=(
        "Run a command line process, and monitor it using LMK. This means that you will be able "
        "to notify yourself when it finishes or finishes with an error, and interrupt it remotely if "
        "you choose."
    ),
)
@click.option(
    "--daemon/--no-daemon",
    default=True,
    help=(
        "Daemonize the monitored process. This is the default, and it means that you can detach "
        "and re-attach to the process while it's running without interrupting it."
    ),
)
@attach_option
@name_option
@notify_on_option()
@click.argument("command", nargs=-1)
@click.pass_context
async def run(
    ctx: click.Context,
    daemon: bool,
    command: List[str],
    attach: bool,
    name: Optional[str],
    notify: str,
):
    if not command:
        click.secho("No command provided", fg="red")
        raise click.Abort

    head, *tail = command
    command = shlex.split(head) + tail

    if name is None:
        name = command[0]

    _check_login()

    manager: JobManager = ctx.obj["manager"]
    job = await manager.create_job(name, notify)
    click.secho(f"Job ID: {job.name}", fg="green", bold=True)

    monitor = ChildMonitor(command)

    if daemon:
        await run_daemon(job.name, monitor, manager, ctx.obj["log_level"])
        if attach:
            exit_code = await attach_interactive(job.name, manager)
            sys.exit(exit_code or 0)
    else:
        await run_foreground(job.name, monitor, manager, ctx.obj["log_level"], attach)


monitor_args = stack_decorators(
    click.argument("pid"),
    attach_option,
    name_option,
    notify_on_option(),
    click.option("-j", "--job", default=None, hidden=True),
)


@async_command(
    cli,
    short_help="Monitor a script that has already been started",
    help=(
        "Monitor a script that has already been started and either paused via Ctrl-Z or "
        "is running in a different terminal."
    ),
)
@monitor_args
@click.pass_context
async def monitor(
    ctx: click.Context,
    pid: str,
    attach: bool,
    name: Optional[str],
    notify: str,
    job: str,
):
    resolved_pid, _ = resolve_pid(pid)

    manager: JobManager = ctx.obj["manager"]
    if name is None:
        proc = psutil.Process(resolved_pid)
        name = proc.cmdline()[0]

    _check_login()

    await check_lldb()

    if job is None:
        job_obj = await manager.create_job(name, notify)
    else:
        job_obj = await manager.get_job(job, not_started=True)
        if job_obj is None:
            raise exc.JobNotFound(job)
        if notify != job_obj.notify_on:
            await manager.update_job(job, notify_on=notify)

    click.secho(f"Job ID: {job_obj.name}", fg="green", bold=True)

    monitor = LLDBProcessMonitor(resolved_pid)

    await run_daemon(job_obj.name, monitor, manager, ctx.obj["log_level"])

    if attach:
        exit_code = await attach_interactive(job_obj.name, manager)
        sys.exit(exit_code or 0)


@async_command(
    cli,
    short_help="Attach to a monitored job",
    help=(
        "Attach to a monitored job, so you will see the output in your terminal in real time. You can "
        "detach from or interrupt the job while attached."
    ),
)
@click.argument("job_id")
@click.pass_context
async def attach(ctx: click.Context, job_id: str):
    manager: JobManager = ctx.obj["manager"]
    job = await manager.get_job(job_id)

    if job is None:
        raise exc.JobNotFound(job_id)

    if not job.is_running():
        raise exc.JobNotRunning(job_id)

    exit_code = await attach_interactive(job.name, manager)
    sys.exit(exit_code or 0)


def pad(value: str, length: int, character: str = " ", **style_kwargs) -> str:
    if len(value) > length:
        return value[: length - 3] + "..."
    return click.style(value + character * (length - len(value)), **style_kwargs)


@async_command(cli, help="List jobs monitored by LMK")
@click.option(
    "-a",
    "--all",
    is_flag=True,
    help="List all jobs; by default only running jobs are shown",
)
@click.pass_context
async def jobs(ctx: click.Context, all: bool):
    manager: JobManager = ctx.obj["manager"]
    jobs = await manager.list_jobs(running_only=not all)

    if not jobs:
        click.echo("No jobs found")
        return

    click.echo(
        " ".join(
            [
                pad("name", 30, bold=True),
                pad("pid", 10, bold=True),
                pad("status", 12, bold=True),
                pad("notify", 10, bold=True),
                pad("started", 30, bold=True),
            ]
        )
    )
    for job in jobs:
        state_kwargs: Dict[str, Any] = {}
        if job.ended_at:
            exit_str = job.exit_code if job.exit_code is not None else "?"
            if job.exit_code == 0:
                state_kwargs = {"fg": "yellow"}
            else:
                state_kwargs = {"fg": "red"}
            state = f"exited ({exit_str})"
        elif job.started_at:
            state = "running"
            state_kwargs = {"fg": "green", "bold": True}
        else:
            state = "not-started"

        notify_on = ""
        notify_on_kwargs = {}
        if job.notify_on == "stop":
            notify_on = "stop"
            notify_on_kwargs = {"fg": "yellow"}
        elif job.notify_on == "error":
            notify_on = "error"
            notify_on_kwargs = {"fg": "red"}

        click.echo(
            " ".join(
                [
                    pad(job.name, 30, bold=True),
                    pad(str(job.pid), 10),
                    pad(state, 12, **state_kwargs),
                    pad(notify_on, 10, **notify_on_kwargs),
                    pad(job.started_at.isoformat() if job.started_at else "", 30),
                ]
            )
        )


@async_command(
    cli,
    short_help="Send a signal to a monitored job",
    help="Send a signal to a monitored job to interrupt or terminate it.",
)
@click.argument("job_id")
@click.option(
    "-s", "--signal", default="SIGINT", help="Signal to send, defaults to SIGINT"
)
@click.pass_context
async def kill(ctx: click.Context, job_id: str, signal: str):
    manager: JobManager = ctx.obj["manager"]
    job = await manager.get_job(job_id)

    if job is None:
        raise exc.JobNotFound(job_id)

    if not job.is_running():
        raise exc.JobNotRunning(job_id)

    signal_value: Optional[int]
    if signal.isdigit():
        signal_value = int(signal)
    else:
        signal_value = getattr(
            signal_module,
            signal.upper(),
            getattr(signal_module, "SIG" + signal.upper(), None),
        )

    if signal_value is None:
        click.secho(f"Invalid signal value: {signal}", fg="red", bold=True)
        raise click.Abort

    await send_signal(manager.socket_file(job.name), signal_value)


@async_command(
    cli,
    short_help="Change the `notify_on` value for a running job",
    help=(
        "Change the `notify_on` value for a running job to a new value. This will set the job to "
        "notify you when it's finished running, exits with an error, or change it to not notify you "
        "if it's currently configured to send you a notification."
    ),
)
@click.argument("job_id")
@notify_on_option("stop")
@click.pass_context
async def notify(ctx: click.Context, job_id: str, notify: str) -> None:
    manager: JobManager = ctx.obj["manager"]
    job = await manager.get_job(job_id)

    if job is None:
        raise exc.JobNotFound(job_id)

    if not job.is_running():
        raise exc.JobNotRunning(job_id)

    await manager.update_job(job.name, notify_on=notify)
    await update_job(manager.socket_file(job.name))


@cli.command(
    short_help="Install the LMK shell plugin",
    help=(
        "Install the LMK shell plugin, which allows you to monitor jobs "
        "using shell syntax like %1, %2, etc."
    ),
)
@click.option(
    "-i",
    "--install",
    default=False,
    is_flag=True,
    help="Install the shell CLI script in the shell profile",
)
@click.option(
    "-u",
    "--uninstall",
    default=False,
    is_flag=True,
    help="Uninstall the shell CLI script from the shell profile",
)
@click.option(
    "-p",
    "--print",
    is_flag=True,
    default=False,
    help=(
        "Print the shell plugin script; this is useful if the automatic installation process "
        "via --install is not working properly."
    ),
)
@click.option(
    "-s",
    "--shell",
    default=None,
    help=(
        "Shell flavor that you're using, e.g. bash or zsh. If this is not passed, "
        "the shell you're currently using will be detected automatically."
    ),
)
@click.pass_context
def shell_plugin(
    ctx: click.Context,
    install: bool,
    uninstall: bool,
    shell: Optional[str],
    print: bool,
) -> None:
    if shell is None:
        shell = detect_shell()

    num_actions = sum([install, uninstall, print])

    if num_actions > 1:
        ctx.fail("Only one of --print, --install, or --uninstall may be provided")
    if num_actions == 0:
        ctx.fail("One of --print, --install, or --uninstall must be provided")

    if print:
        script = get_shell_cli_script(shell)
        click.echo(script)
        click.echo(
            textwrap.dedent(
                """
        # THIS SHOULD BE SOURCED BY YOUR SHELL
        # E.g. . <(lmk shell-plugin --print)
        # To add to your shell profile, use the --install flag
        """
            ).strip()
        )
        return

    profile_file = shell_profile_file(shell)

    if install:
        install_script(profile_file)
        click.secho(
            f"Shell plugin installed successfully. Run "
            f"`. {profile_file}` or open a new shell to see the "
            f"changes take effect.",
            fg="green",
            bold=True,
        )
        return

    if uninstall:
        uninstall_script(profile_file)
        click.secho("Shell plugin uninstalled successfully", fg="green", bold=True)
