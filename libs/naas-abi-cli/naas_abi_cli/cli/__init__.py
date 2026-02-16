import os
import subprocess
import sys

import click

from .agent import agent
from .chat import chat
from .config import config
from .deploy import deploy
from .init import init
from .module import module
from .new import new
from .run import run
from .secret import secrets
from .setup import setup


@click.group("abi")
def _main():
    pass


_main.add_command(secrets)
_main.add_command(config)
_main.add_command(module)
_main.add_command(agent)
_main.add_command(chat)
_main.add_command(new)
_main.add_command(init)
_main.add_command(deploy)
_main.add_command(run)
_main.add_command(setup)
ran = False


def main():
    global ran
    if ran:
        return
    ran = True

    # Check how the project is being runned.
    if os.getenv("LOCAL_UV_RAN") is None:
        if "pyproject.toml" in os.listdir(os.getcwd()):
            with open("pyproject.toml", "r") as file:
                if "naas-abi-cli" in file.read():
                    arguments = (
                        "uv run --active python -m naas_abi_cli.cli".split(" ")
                        + sys.argv[1:]
                    )
                    try:
                        subprocess.run(
                            arguments,
                            cwd=os.getcwd(),
                            env={**os.environ, "LOCAL_UV_RAN": "true"},
                            check=True,
                        )
                    except Exception:
                        pass

                    return
    _main()


main()
main()
