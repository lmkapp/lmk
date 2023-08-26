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
    click.option("-l", "--log-level", default="WARN", help="Log level"),
    click.option("-b", "--base-path", default=os.path.expanduser("~/.lmk")),
)


@click.group()
@cli_args
@click.pass_context
def cli(ctx: click.Context, log_level: str, base_path: str):
    setup_logging(level=log_level)
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["manager"] = JobManager(base_path)


@cli.command()
@click.option("--force/--no-force", is_flag=True, default=True)
def login(force):
    instance = get_instance()
    instance.login(force=force)


attach_option = click.option(
    "--attach/--no-attach", default=True, help="Attach to the process"
)

name_option = click.option("-N", "--name", default=None)


def notify_on_option(default: str = "none"):
    return click.option(
        "-n", "--notify", default=default, type=click.Choice(["stop", "error", "none"])
    )


@async_command(cli)
@click.option("--daemon/--no-daemon", default=True, help="Daemonize the process")
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
    click.argument("pid"),
    attach_option,
    name_option,
    notify_on_option(),
    click.option("-j", "--job", default=None),
)


@async_command(cli)
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


@async_command(cli)
@click.argument("job_id")
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


@async_command(cli)
@click.option("-a", "--all", is_flag=True, help="List all jobs")
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


@async_command(cli)
@click.argument("job_id")
@click.option("-s", "--signal", default="SIGINT", help="Signal to send")
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


@async_command(cli)
@click.argument("job_id")
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
@click.option("-p", "--print", is_flag=True, default=False)
@click.option("-s", "--shell", default=None)
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
