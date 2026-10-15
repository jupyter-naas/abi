import os
from pathlib import Path

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .remote_module import is_remote_module, target_dir
from .utils import module_package_name, to_pascal_case


@new.command("agent")
@click.argument("agent_name", required=True)
@click.argument("agent_path", required=False, default=".")
def _new_agent(agent_name: str, agent_path: str = "."):
    """Create an agent: an SDK IntentAgent inside a remote module, a
    naas_abi_core Agent inside an in-engine one."""
    remote = is_remote_module(target_dir(agent_path))
    new_agent(agent_name, agent_path, remote=remote)
    if remote:
        name = to_pascal_case(agent_name)
        click.echo(
            f"Created {name}Agent.py (naas_abi_sdk). To publish it, declare it in "
            "ABIModule.agents with AgentDescriptor(NAME, DESCRIPTION, "
            'capabilities=("agent.invoke.v1",)) and bind it in on_initialized: '
            "self.expose_agent(NAME, (await create_agent(self.engine, MODULE_ID))"
            ".as_handler())."
        )


def new_agent(
    agent_name: str,
    agent_path: str = ".",
    extra_values: dict | None = None,
    remote: bool = False,
):
    """``remote``: an SDK agent for a remote module (no naas_abi_core)."""
    if extra_values is None:
        extra_values = {}
    agent_name = to_pascal_case(agent_name)

    if agent_path == ".":
        agent_path = os.getcwd()

    if not os.path.exists(agent_path):
        os.makedirs(agent_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__),
            "cli/new/templates/remote_agent" if remote else "cli/new/templates/agent",
        ),
        destination_path=agent_path,
    )

    if "module_name_snake" not in extra_values:
        extra_values["module_name_snake"] = (
            module_package_name(Path(agent_path).resolve()) or "your_module_name"
        )

    copier.copy(values={"agent_name_pascal": to_pascal_case(agent_name)} | extra_values)
