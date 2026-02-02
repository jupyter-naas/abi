import os

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_pascal_case


@new.command("agent")
@click.argument("agent_name", required=True)
@click.argument("agent_path", required=False, default=".")
def _new_agent(agent_name: str, agent_path: str = "."):
    new_agent(agent_name, agent_path)


def new_agent(
    agent_name: str,
    agent_path: str = ".",
    extra_values: dict = {},
):
    agent_name = to_pascal_case(agent_name)

    if agent_path == ".":
        agent_path = os.getcwd()

    if not os.path.exists(agent_path):
        os.makedirs(agent_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/agent"
        ),
        destination_path=agent_path,
    )

    if "module_name_snake" not in extra_values:
        extra_values["module_name_snake"] = "your_module_name"

    copier.copy(values={"agent_name_pascal": to_pascal_case(agent_name)} | extra_values)
