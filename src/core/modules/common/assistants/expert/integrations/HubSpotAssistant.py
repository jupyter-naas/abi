from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import HubSpotIntegration
from src.core.modules.common.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.core.modules.common.assistants.foundation.SupportAssistant import create_support_agent
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A HubSpot Assistant with access to HubSpot Integration tools."
AVATAR_URL = "https://www.hubspot.com/hubfs/HubSpot_Logos/HubSpot-Inversed-Favicon.png"
SYSTEM_PROMPT = f"""
You are a HubSpot Assistant with access to HubSpot Integration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with HubSpot services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_hubspot_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
):
    # Init
    tools = []
    agents = []

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
        
    # Set model
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Add tools
    if secret.get('HUBSPOT_ACCESS_TOKEN'):    
        hubspot_integration_config = HubSpotIntegrationConfiguration(access_token=secret.get('HUBSPOT_ACCESS_TOKEN'))
        tools += HubSpotIntegration.as_tools(hubspot_integration_config)

    # Add agents
    agents.append(create_support_agent(AgentSharedState(thread_id=2), agent_configuration))
    
    return HubSpotAssistant(
        name="hubspot_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class HubSpotAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "hubspot", 
        name: str = "HubSpot Assistant", 
        description: str = "API endpoints to call the HubSpot assistant completion.", 
        description_stream: str = "API endpoints to call the HubSpot assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)