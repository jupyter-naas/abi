import click
from naas_abi_core import logger


@click.command("chat")
@click.argument("module-name", type=str, default="")
@click.argument("agent-name", type=str, default="")
def chat(module_name: str = "", agent_name: str = ""):
    from naas_abi_core.services.event.local_identity import bind_local_identity

    # Events published while chatting (git agents, tool calls) name the
    # terminal's git author, hashed, and are marked triggered via "cli".
    with bind_local_identity():
        _chat(module_name, agent_name)


def _chat(module_name: str, agent_name: str) -> None:
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()

    if module_name == "" and agent_name == "":
        module_name, agent_name = engine.configuration.default_agent.split(" ")

    engine.load(module_names=[module_name])

    from naas_abi_core.apps.terminal_agent.main import run_agent

    if module_name not in engine.modules:
        raise ValueError(f"Module {module_name} not found")

    logger.debug(f"Module agents: {engine.modules[module_name].agents}")

    for agent_class in engine.modules[module_name].agents:
        logger.debug(f"Agent class: {agent_class.__name__}")
        if agent_class.__name__ == agent_name:
            run_agent(agent_class.New())  # type: ignore[attr-defined]
            break
