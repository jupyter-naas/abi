from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret
from fastapi import APIRouter
from src.marketplace.modules.applications.naas.integrations import NaasIntegration
from src.marketplace.modules.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from typing import Optional
from enum import Enum
from pydantic import SecretStr

NAME = "Naas"
MODEL = "gpt-4o"
TEMPERATURE = 0
DESCRIPTION = "Manage all resources on Naas: workspaces, agents, ontologies, users, secrets, storage."
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = """
You are a Naas Agent with access to NaasIntegration tools to perform actions on Naas workspaces.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Naas services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""
SUGGESTIONS: list[str] = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    tools: list = []
    agents: list = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Add tools
    if secret.get("NAAS_API_KEY"):
        naas_integration_config = NaasIntegrationConfiguration(
            api_key=secret.get("NAAS_API_KEY")
        )
        tools += NaasIntegration.as_tools(naas_integration_config)

    return NaasAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class NaasAgent(Agent):
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
