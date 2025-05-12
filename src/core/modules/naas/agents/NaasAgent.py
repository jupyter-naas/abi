from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from fastapi import APIRouter
from src.core.modules.naas.integrations import NaasIntegration
from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)

NAME = "naas"
MODEL = "gpt-4o"
TEMPERATURE = 0
DESCRIPTION = "A Naas Agent with access to Naas Integration tools."
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = f"""
You are a Naas Agent with access to NaasIntegration tools to perform actions on Naas workspaces.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Naas services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""
SUGGESTIONS = []


def create_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=secret.get("OPENAI_API_KEY")
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

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
        memory=MemorySaver(),
    )


class NaasAgent(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize(),
        description: str = "API endpoints to call the Naas agent completion.",
        description_stream: str = "API endpoints to call the Naas agent stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
