from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config
from fastapi import APIRouter
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.integrations.OpenAIIntegration import OpenAIIntegrationConfiguration
from src.core.integrations.PowerPointIntegration import PowerPointIntegrationConfiguration
from src.core.workflows.powerpoint.UpdateOrganizationSlidesWorkflow import UpdateOrganizationSlidesWorkflow, UpdateOrganizationSlidesWorkflowConfiguration

DESCRIPTION = "A PowerPoint Assistant for creating and managing presentations."
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg/2203px-Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg.png"
SYSTEM_PROMPT = f"""You are a McKinsey & Company consultant very skilled in creating PowerPoint presentations.
Your goal is to help the user creating a quality brief to create or update a PowerPoint presentation using the tools provided.

When introducing yourself:
1. State your goal
2. List your available tools with descriptions and template names for each tool

Before creating or updating a presentation, ensure you gather required information needed from the user.

{RESPONSIBILITIES_PROMPT}
"""

def create_powerpoint_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    if secret.get('NAAS_API_KEY') and config.workspace_id != '' and config.storage_name != '' and secret.get('OPENAI_API_KEY'):
        updateOrganizationSlidesWorkflow = UpdateOrganizationSlidesWorkflow(UpdateOrganizationSlidesWorkflowConfiguration(
            powerpoint_integration_config=PowerPointIntegrationConfiguration(),
            naas_integration_config=NaasIntegrationConfiguration(
                api_key=secret.get('NAAS_API_KEY')
            ),
            openai_integration_config=OpenAIIntegrationConfiguration(
                api_key=secret.get('OPENAI_API_KEY')
            )
        ))
        tools += updateOrganizationSlidesWorkflow.as_tools()

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
        api_key=secret.get('OPENAI_API_KEY'),
        temperature=0
    )
    # Add agents
    agents.append(create_support_assistant(agent_shared_state, agent_configuration))
    
    return PowerPointAssistant(
        name="powerpoint_assistant",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 

class PowerPointAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "powerpoint", 
        name: str = "PowerPoint Assistant", 
        description: str = "API endpoints to call the PowerPoint assistant completion.", 
        description_stream: str = "API endpoints to call the PowerPoint assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags) 