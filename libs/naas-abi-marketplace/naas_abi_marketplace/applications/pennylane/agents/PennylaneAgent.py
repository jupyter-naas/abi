from enum import Enum
from typing import Optional

from fastapi import APIRouter
from langchain_openai import ChatOpenAI
from naas_abi import secret
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from naas_abi_marketplace.applications.pennylane.integrations import (
    PennylaneIntegration,
)
from naas_abi_marketplace.applications.pennylane.integrations.PennylaneIntegration import (
    PennylaneIntegrationConfiguration,
)
from pydantic import SecretStr

NAME = "Pennylane"
DESCRIPTION = "A Pennylane Agent for managing accounting and financial operations."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://logo.clearbit.com/pennylane.tech"
SYSTEM_PROMPT = """Tu es un agent Pennylane avec accès aux outils d'intégration Pennylane.
Si tu n'as pas accès aux outils, demande à l'utilisateur de configurer son PENNYLANE_API_TOKEN dans le fichier .env.
Sois toujours clair et professionnel dans ta communication en aidant les utilisateurs à gérer leurs données comptables.
Fournis toujours tout le contexte (réponse des outils, brouillon, etc.) à l'utilisateur dans ta réponse finale.
"""


def create_agent(
    agent_shared_state: AgentSharedState | None = None,
    agent_configuration: AgentConfiguration | None = None,
):
    # Init
    tools: list = []
    agents: list = []

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get("OPENAI_API_KEY")),
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Add integration based on available credentials
    if secret.get("PENNYLANE_API_TOKEN"):
        integration_config = PennylaneIntegrationConfiguration(
            api_key=secret.get("PENNYLANE_API_TOKEN")
        )
        tools += PennylaneIntegration.as_tools(integration_config)

        return PennylaneAgent(
            name=NAME,
            description=DESCRIPTION,
            chat_model=model,
            tools=tools,
            agents=agents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=MemorySaver(),
        )


class PennylaneAgent(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize().replace("_", " "),
        description: str = "API endpoints to call the Naas agent completion.",
        description_stream: str = "API endpoints to call the Naas agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
