import sys

from lmk.constants import DOCS_ONLY


def check_cli_deps() -> None:
    if DOCS_ONLY:
        return

    try:
        import aiosqlite
        import click
        import psutil
        import sqlalchemy
    except ImportError:
        print(
            "Required modules for the LMK CLI were not found. Run "
            "`pip install 'lmkapp[cli]'` to install required extras.\n\n"
            "See the docs for more details: https://docs.lmkapp.dev/docs/cli/process"
        )

        sys.exit(1)
