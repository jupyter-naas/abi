import sys

import click

from .bootstrap import maybe_rerun_in_project_context
from .agent import agent
from .call import call
from .chat import chat
from .config import config
from .deploy import deploy
from .docs import docs
from .init import init
from .module import module
from .new import new
from .run import run
from .secret import secrets
from .setup import setup
from .stack import logs, stack, start, stop


@click.group("abi")
def _main():
    pass


_main.add_command(secrets)
_main.add_command(config)
_main.add_command(docs)
_main.add_command(module)
_main.add_command(agent)
_main.add_command(call)
_main.add_command(chat)
_main.add_command(new)
_main.add_command(init)
_main.add_command(deploy)
_main.add_command(run)
_main.add_command(setup)
_main.add_command(start)
_main.add_command(stop)
_main.add_command(logs)
_main.add_command(stack)
ran = False


def main():
    global ran
    if ran:
        return
    ran = True

    if maybe_rerun_in_project_context(sys.argv[1:]):
        return

    _main()


if __name__ == "__main__":
    main()
