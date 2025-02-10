from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import NaasIntegration
from src.core.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Naas Assistant with access to Naas Integration tools."
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = f"""
You are a Naas Assistant with access to NaasIntegration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Naas services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_naas_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
    
    # Add tools
    if secret.get('NAAS_API_KEY'):    
        naas_integration_config = NaasIntegrationConfiguration(api_key=secret.get('NAAS_API_KEY'))
        tools += NaasIntegration.as_tools(naas_integration_config)

    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=2), agent_configuration))
    
    return NaasAssistant(
        name="naas_assistant",
        description="Use to manage Naas workspace, plugins and ontologies",
        chat_model=model,
        tools=tools,
        agents=agents,  
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    )

class NaasAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "naas", 
        name: str = "Naas Assistant", 
        description: str = "API endpoints to call the Naas assistant completion.", 
        description_stream: str = "API endpoints to call the Naas assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)