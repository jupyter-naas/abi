from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import HubSpotIntegration
from src.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.integrations.StripeIntegration import StripeIntegrationConfiguration
from src.integrations.PostgresIntegration import PostgresIntegrationConfiguration
from src.workflows.sales.HubSpotWorkflows import HubSpotWorkflows, HubSpotWorkflowsConfiguration

DESCRIPTION = "A Sales Assistant that helps manage and qualify contacts for sales representatives."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/sales_conversion.png"
SYSTEM_PROMPT = f"""
You are a Sales Assistant.
Your role is to manage and optimize the list of people who interacted with the content, ensuring to extract only the most qualified contacts to feed the sales representatives.

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""

def create_sales_assistant(
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
    hubspot_access_token = secret.get('HUBSPOT_ACCESS_TOKEN')
    if hubspot_access_token:
        hubspot_integration_config = HubSpotIntegrationConfiguration(access_token=hubspot_access_token)
        hubspot_workflows = HubSpotWorkflows(HubSpotWorkflowsConfiguration(
            hubspot_integration_config=hubspot_integration_config
        ))
        tools += hubspot_workflows.as_tools()
    
    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=1), agent_configuration))

    return SalesAssistant(
        name="sales_assistant", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class SalesAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "sales", 
        name: str = "Sales Assistant", 
        description: str = "API endpoints to call the Sales assistant completion.", 
        description_stream: str = "API endpoints to call the Sales assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)