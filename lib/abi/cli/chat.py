import click
from abi import logger


@click.command("chat")
@click.argument("module-name", type=str, required=True, default="chatgpt")
@click.argument("agent-name", type=str, required=True, default="ChatGPTAgent")
def chat(module_name: str, agent_name: str):
    from abi.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=[module_name])

    from abi.apps.terminal_agent.main import run_agent

    logger.debug(f"Module agents: {engine.modules[module_name].agents}")

    for agent_class in engine.modules[module_name].agents:
        logger.debug(f"Agent class: {agent_class.__name__}")
        if agent_class.__name__ == agent_name:
            run_agent(agent_class.New())
            break
