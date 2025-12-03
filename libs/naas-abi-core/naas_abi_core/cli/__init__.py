import click

from .agent import agent
from .chat import chat
from .config import config
from .init import init
from .module import module
from .new import new
from .secret import secrets

# from dotenv import load_dotenv

# load_dotenv()


@click.group("abi")
def main():
    pass


# @main.command("chat")
# @click.option("--module-name", type=str, required=True, default="chatgpt")
# @click.option("--agent-name", type=str, required=True, default="ChatGPTAgent")
# def chat(module_name: str, agent_name: str):
#     from naas_abi_core.engine.Engine import Engine

#     engine = Engine()
#     engine.load(module_names=[module_name])

#     from naas_abi_core.apps.terminal_agent.main import run_agent

#     logger.debug(f"Module agents: {engine.modules[module_name].agents}")

#     for agent_class in engine.modules[module_name].agents:
#         logger.debug(f"Agent class: {agent_class.__name__}")
#         if agent_class.__name__ == agent_name:
#             run_agent(agent_class.New())
#             break


# Add the secrets group to the main abi group


main.add_command(secrets)
main.add_command(config)
main.add_command(module)
main.add_command(agent)
main.add_command(chat)
main.add_command(new)
main.add_command(init)

# if __name__ == "__main__":
main()
