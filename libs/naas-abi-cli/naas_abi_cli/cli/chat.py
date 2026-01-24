import click
from naas_abi_core import logger


@click.command("chat")
@click.argument("module-name", type=str, default=None)
@click.argument("agent-name", type=str, default=None)
def chat(module_name: str | None, agent_name: str | None):
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()

    if module_name is None and agent_name is None:
        module_name, agent_name = engine.configuration.default_agent.split(" ")

    engine.load(module_names=[module_name])

    from naas_abi_core.apps.terminal_agent.main import run_agent

    if module_name not in engine.modules:
        raise ValueError(f"Module {module_name} not found")

    logger.debug(f"Module agents: {engine.modules[module_name].agents}")

    for agent_class in engine.modules[module_name].agents:
        logger.debug(f"Agent class: {agent_class.__name__}")
        if agent_class.__name__ == agent_name:
            run_agent(agent_class.New())
            break
