import os

import click
from abi import logger

# from dotenv import load_dotenv

# load_dotenv()


@click.group("abi")
def main():
    pass


@click.group("secrets")
def secrets():
    pass


@secrets.group("naas")
def naas():
    pass


@naas.command("push-env-as-base64")
@click.option(
    "--naas-api-key", type=str, required=True, default=os.getenv("NAAS_API_KEY")
)
@click.option("--naas-api-url", type=str, required=True, default="https://api.naas.ai")
@click.option("--naas-secret-name", type=str, required=True, default="abi_secrets")
@click.option("--env-file", type=str, required=True, default=".env.prod")
def push_env_to_naas(naas_api_key, naas_api_url, naas_secret_name, env_file):
    import base64

    from abi.services.secret.adaptors.secondary.NaasSecret import NaasSecret

    naas_secret = NaasSecret(naas_api_key, naas_api_url)

    envfile_content = ""

    with open(env_file, "r") as envfile:
        envfile_content = envfile.read()

    print(envfile_content)

    base64_content = base64.b64encode(envfile_content.encode("utf-8")).decode("utf-8")
    naas_secret.set(naas_secret_name, base64_content)

    print(f"Pushed {env_file} to Naas as base64 secret {naas_secret_name}")


@naas.command("list")
@click.option(
    "--naas-api-key", type=str, required=True, default=os.getenv("NAAS_API_KEY")
)
@click.option("--naas-api-url", type=str, required=True, default="https://api.naas.ai")
def list_secrets(naas_api_key, naas_api_url):
    from abi.services.secret.adaptors.secondary.NaasSecret import NaasSecret

    naas_secret = NaasSecret(naas_api_key, naas_api_url)

    naas_secret.list()

    for key, value in naas_secret.list().items():
        print(f"{key}: {value}")


@naas.command("get-base64-env")
@click.option(
    "--naas-api-key", type=str, required=True, default=os.getenv("NAAS_API_KEY")
)
@click.option("--naas-api-url", type=str, required=True, default="https://api.naas.ai")
@click.option("--naas-secret-name", type=str, required=True, default="abi_secrets")
def get_secret(naas_api_key, naas_api_url, naas_secret_name):
    from abi.services.secret.adaptors.secondary.Base64Secret import Base64Secret
    from abi.services.secret.adaptors.secondary.NaasSecret import NaasSecret

    naas_secret = NaasSecret(naas_api_key, naas_api_url)
    base64_secret = Base64Secret(naas_secret, naas_secret_name)

    for key, value in base64_secret.list().items():
        # If value is multiline
        if "\n" in value:
            print(f'{key}="{value}"')
        else:
            print(f"{key}={value}")


@naas.command("chat")
@click.option("--module-name", type=str, required=True, default="chatgpt")
@click.option("--agent-name", type=str, required=True, default="ChatGPTAgent")
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


# Add the secrets group to the main abi group
main.add_command(secrets)
main.add_command(chat)

if __name__ == "__main__":
    main()
