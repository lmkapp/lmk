from lmk.cli_deps import check_cli_deps

check_cli_deps()

import asyncio  # noqa: E402
import sys  # noqa: E402
from typing import List, Any, Dict  # noqa: E402

import click  # noqa: E402
import psutil  # noqa: E402

from lmk.cli import cli  # noqa: E402
from lmk.process.manager import JobManager  # noqa: E402
from lmk.process.shell_plugin import resolve_pid  # noqa: E402
from lmk.utils import shlex_join  # noqa: E402


def format_params(values: Dict[str, Any], params: List[click.Parameter]) -> List[str]:
    params_by_name = {param.name: param for param in params}

    out: List[str] = []
    for key, value in values.items():
        if key not in params_by_name:
            continue

        param = params_by_name[key]
        if value == param.default:
            continue

        if isinstance(param, click.Argument):
            if isinstance(value, tuple):
                out.extend(value)
            else:
                out.append(value)
        elif param.type == click.BOOL:
            out.append(param.opts[0] if value else param.secondary_opts[0])
        else:
            out.append(param.opts[-1])
            out.append(value)

    return out


async def process_cmd(
    ctx: click.Context,
    root_args: List[str],
) -> None:
    manager = JobManager(ctx.params["base_path"])

    await manager.setup()

    all_args = [*ctx.protected_args, *ctx.args]
    cmd_name, cmd, cmd_args = cli.resolve_command(ctx, all_args)
    with cmd.make_context(cmd_name, cmd_args, parent=ctx) as sub_ctx:
        cmd_params = cmd.get_params(sub_ctx)
        if cmd_name == "monitor":
            pid, shell_job_id = resolve_pid(sub_ctx.params["pid"])
            name = sub_ctx.params["name"]
            if name is None:
                proc = psutil.Process(pid)
                name = proc.cmdline()[0]

            if sub_ctx.params["job"] is None:
                job = await manager.create_job(name)
                job_id = job.name
            else:
                job_id = sub_ctx.params["job"]

            new_params = {
                **sub_ctx.params,
                "job": job_id,
                "pid": str(pid),
                "attach": False,
            }
            new_args = root_args.copy()
            new_args.append(cmd_name)
            new_args.extend(format_params(new_params, cmd_params))
            print(
                "CMD" if sub_ctx.params["attach"] else "LASTCMD", shlex_join(new_args)
            )

            print("DISOWN", shell_job_id)

            if sub_ctx.params["attach"]:
                new_args = root_args.copy()
                new_args.append("attach")
                attach_command = cli.get_command(ctx, "attach")
                attach_params = attach_command.get_params(ctx)
                new_attach_params = {"job_id": job_id}
                new_args.extend(format_params(new_attach_params, attach_params))
                print("LASTCMD", shlex_join(new_args))
        else:
            out_args = root_args.copy()
            out_args.append(cmd_name)
            out_args.extend(format_params(sub_ctx.params, cmd_params))
            print("LASTCMD", shlex_join(out_args))


async def main(args: List[str]) -> int:
    try:
        with cli.make_context("lmk", args=args) as ctx:
            out_args = format_params(ctx.params, cli.get_params(ctx))
            await process_cmd(ctx, out_args)
            return 0
    except click.exceptions.Abort:
        click.echo("Aborted!", file=sys.stderr)
        return 1
    except click.exceptions.ClickException as err:
        err.show()
        return err.exit_code
    except click.exceptions.Exit as err:
        return err.exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
