import click
import os
import psutil
import shlex
import signal as signal_module
import sys
import textwrap
from typing import List, Optional

from lmk.instance import get_instance
from lmk.process.attach import attach_interactive
from lmk.process.child_monitor import ChildMonitor
from lmk.process.client import send_signal, set_notify_on
from lmk.process.daemon import ProcessMonitorController
from lmk.process.lldb_monitor import LLDBProcessMonitor
from lmk.process.manager import JobManager
from lmk.process.run import run_foreground, run_daemon
from lmk.shell_plugin import (
    detect_shell,
    install_script,
    uninstall_script,
    shell_profile_file,
    resolve_pid,
    get_shell_cli_script,
)
from lmk.utils.click import async_command
from lmk.utils.decorators import stack_decorators
from lmk.utils.logging import setup_logging


cli_args = stack_decorators(
    click.option("-l", "--log-level", default="WARN", help="Log level, defaults to WARN"),
    click.option("-b", "--base-path", default=os.path.expanduser("~/.lmk"), help="Path to the LMK configuration directory; defaults to ~/.lmk"),
)


@click.group(
    help=(
        "The LMK Command Line Interface. This allows you to monitor command-line processes remotely "
        "via the LMK web app."
    )
)
@cli_args
@click.pass_context
def cli(ctx: click.Context, log_level: str, base_path: str):
    setup_logging(level=log_level)
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["manager"] = JobManager(base_path)


@cli.command(
    help=(
        "Authenticate with the LMK API. This should typically be the first command you run when "
        "using the CLI for the first time, and it allows you to use the other commands."
    )
)
@click.option(
    "--force/--no-force",
    is_flag=True,
    default=True,
    help=(
        "By default, this will be a no-op if you are already logged in. Pass --force to "
        "force the CLI to re-authenticate with LMK."
    )
)
def login(force):
    instance = get_instance()
    instance.login(force=force)


attach_option = click.option(
    "--attach/--no-attach",
    default=True,
    help=(
        "Attach to the process, meaning you will see the logs from the process appearing in your "
        "console in real time. You can detach at any time, at which point you can choose to let the "
        "process keep running or interrupt it. After detaching, you will also be able to re-attach at any "
        "time while the process is running."
    )
)

name_option = click.option(
    "-N",
    "--name",
    default=None,
    help=(
        "Job name for the job you want to run. This will be visible in the LMK dashboard, "
        "and it can be passed to other commands that take a job ID such as `attach`, `kill`, etc. "
        "If not passed, a name will be generated."
    )
)


def notify_on_option(default: str = "none"):
    return click.option(
        "-n", "--notify", default=default, type=click.Choice(["stop", "error", "none"]),
        help=(
            "Set the initial `notify_on` value for the process. If `stop`, you will get a notification "
            "whenever the process completes for any reason. If `error`, you will only get a notification "
            "if it exists with a non-zero status code. If `none`, you will note be notified at all, but will "
            "still be able to monitor the process of the script via the LMK web app. This can be changed after "
            "launching the process initially, so if you omit it initially you can always choose to notify yourself "
            "later."
        )
    )


@async_command(
    cli,
    short_help="Run a command line process, and monitor it using LMK",
    help=(
        "Run a command line process, and monitor it using LMK. This means that you will be able "
        "to notify yourself when it finishes or finishes with an error, and interrupt it remotely if "
        "you choose."
    )
)
@click.option(
    "--daemon/--no-daemon",
    default=True,
    help=(
        "Daemonize the monitored process. This is the default, and it means that you can detach "
        "and re-attach to the process while it's running without interrupting it."
    )
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

    manager = ctx.obj["manager"]
    job = manager.create_job(name)
    click.secho(f"Job ID: {job.job_id}", fg="green", bold=True)

    monitor = ChildMonitor(command)
    controller = ProcessMonitorController(job.job_id, -1, monitor, job.job_dir, notify)

    if daemon:
        await run_daemon(job, controller, ctx.obj["log_level"])
        if attach:
            exit_code = await attach_interactive(job.job_dir)
            sys.exit(exit_code or 0)
    else:
        await run_foreground(job, controller, ctx.obj["log_level"], attach)


monitor_args = stack_decorators(
    click.argument(
        "pid",
        # help=(
        #     "PID of the process that you'd like to monitor. If you are using the shell plugin "
        #     "you can use bash jobs syntax e.g. %1. See the `shell-plugin` command for details. "
        #     "Note that if you use jobs syntax, the process will be disowned by your terminal, "
        #     "so if you close your terminal it will continue to run. Use the `lmk kill` command "
        #     "to interrupt or terminate a job that you've monitored via this command, or interrupt "
        #     "it via the LMK web app."
        # )
    ),
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
    )
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
    pid, _ = resolve_pid(pid)

    manager: JobManager = ctx.obj["manager"]
    if name is None:
        proc = psutil.Process(pid)
        name = proc.cmdline()[0]

    if job is None:
        job_obj = manager.create_job(name)
    else:
        job_obj = manager.get_not_started_job(job)

    click.secho(f"Job ID: {job_obj.job_id}", fg="green", bold=True)

    monitor = LLDBProcessMonitor()

    controller = ProcessMonitorController(
        job_obj.job_id, pid, monitor, job_obj.job_dir, notify
    )

    await run_daemon(job_obj, controller, ctx.obj["log_level"])

    if attach:
        exit_code = await attach_interactive(job_obj.job_dir)
        sys.exit(exit_code or 0)


@async_command(
    cli,
    short_help="Attach to a monitored job",
    help=(
        "Attach to a monitored job, so you will see the output in your terminal in real time. You can "
        "detach from or interrupt the job while attached."
    )
)
@click.argument(
    "job_id",
    # help="ID of a job that you'd like to attach to. Use the `lmk jobs` command to list running jobs."
)
@click.pass_context
async def attach(ctx: click.Context, job_id: str):
    manager = ctx.obj["manager"]
    job = await manager.get_job(job_id)

    if not job.running:
        click.secho(f"Job is not running: {job_id}", fg="red")
        raise click.Abort

    exit_code = await attach_interactive(job.job_dir)
    sys.exit(exit_code or 0)


def pad(value: str, length: int, character: str = " ") -> str:
    if len(value) > length:
        return value[: length - 3] + "..."
    return value + character * (length - len(value))


@async_command(
    cli,
    help="List jobs monitored by LMK"
)
@click.option("-a", "--all", is_flag=True, help="List all jobs; by default only running jobs are shown")
@click.pass_context
async def jobs(ctx: click.Context, all: bool):
    manager = ctx.obj["manager"]
    if all:
        job_ids = manager.get_all_job_ids()
        jobs = manager.get_jobs(job_ids)
    else:
        jobs = manager.list_running_jobs()

    print(
        pad("id", 30),
        pad("pid", 10),
        pad("status", 12),
        pad("notify", 10),
        pad("started", 30),
    )
    async for job in jobs:
        print(
            pad(str(job.job_id), 30),
            pad(str(job.target_pid), 10),
            pad("running    " if job.running else "not-running", 12),
            pad(job.notify_on, 10),
            pad(job.started_at.isoformat(), 30),
        )


@async_command(
    cli,
    short_help="Send a signal to a monitored job",
    help="Send a signal to a monitored job to interrupt or terminate it."
)
@click.argument(
    "job_id",
    # help="ID of the job you'd like to kill. Use `lmk jobs` to list running jobs."
)
@click.option("-s", "--signal", default="SIGINT", help="Signal to send, defaults to SIGINT")
@click.pass_context
async def kill(ctx: click.Context, job_id: str, signal: str):
    manager = ctx.obj["manager"]
    job = await manager.get_job(job_id)

    if not job.running:
        click.secho(f"Job is not running: {job_id}", fg="red")
        raise click.Abort

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

    socket_path = os.path.join(job.job_dir, "daemon.sock")
    await send_signal(socket_path, signal_value)


@async_command(
    cli,
    short_help="Change the `notify_on` value for a running job",
    help=(
        "Change the `notify_on` value for a running job to a new value. This will set the job to "
        "notify you when it's finished running, exits with an error, or change it to not notify you "
        "if it's currently configured to send you a notification."
    )
)
@click.argument(
    "job_id",
    # help="ID of the running job to set the `notify_on` value for; use `lmk jobs` to list running jobs"
)
@notify_on_option("stop")
@click.pass_context
async def notify(ctx: click.Context, job_id: str, notify: str) -> None:
    manager = ctx.obj["manager"]
    job = await manager.get_job(job_id)

    if not job.running:
        click.secho(f"Job is not running: {job_id}", fg="red")
        raise click.Abort

    socket_path = os.path.join(job.job_dir, "daemon.sock")
    await set_notify_on(socket_path, notify)


@cli.command(
    short_help="Install the LMK shell plugin",
    help=(
        "Install the LMK shell plugin, which allows you to monitor jobs "
        "using shell syntax like %1, %2, etc."
    )
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
    "-p", "--print",
    is_flag=True,
    default=False,
    help=(
        "Print the shell plugin script; this is useful if the automatic installation process "
        "via --install is not working properly."
    )
)
@click.option(
    "-s",
    "--shell",
    default=None,
    help=(
        "Shell flavor that you're using, e.g. bash or zsh. If this is not passed, "
        "the shell you're currently using will be detected automatically."
    )
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
