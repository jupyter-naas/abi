from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config
from fastapi import APIRouter
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.integrations.PowerPointIntegration import PowerPointIntegrationConfiguration
from src.workflows.powerpoint_assistant.GenerateSlidesWorkflow import GenerateSlidesWorkflow, GenerateSlidesWorkflowConfiguration
from src.workflows.powerpoint_assistant.UpdateOrganizationSlidesWorkflow import UpdateOrganizationSlidesWorkflow, UpdateOrganizationSlidesWorkflowConfiguration

DESCRIPTION = "A PowerPoint Assistant for creating and managing presentations."
AVATAR_URL = "https://logo.clearbit.com/microsoft.com"
SYSTEM_PROMPT = f"""
You are a PowerPoint Assistant with specialized tools for creating and updating presentations.

When introducing yourself:
1. State your name and role
2. List your available tools with descriptions and template names for each tool

Before proceeding with any task, ensure you gather comprehensive information from users by:
- Asking clarifying questions
- Confirming requirements
- Understanding the desired presentation style and content

Communication Guidelines:
- Maintain clear, concise, and professional communication
- Provide step-by-step guidance when needed
- Include detailed context in responses, including:
  - Tool execution results
  - Draft content
  - Any relevant presentation previews
  - Status updates

{RESPONSIBILITIES_PROMPT}
"""

def create_powerpoint_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    if secret.get('NAAS_API_KEY') and config.workspace_id != '' and config.storage_name != '':
        generateSlidesWorkflow = GenerateSlidesWorkflow(GenerateSlidesWorkflowConfiguration(
            powerpoint_integration_config=PowerPointIntegrationConfiguration(),
            naas_integration_config=NaasIntegrationConfiguration(
                api_key=secret.get('NAAS_API_KEY')
            )
        ))
        tools += generateSlidesWorkflow.as_tools()

        updateOrganizationSlidesWorkflow = UpdateOrganizationSlidesWorkflow(UpdateOrganizationSlidesWorkflowConfiguration(
            powerpoint_integration_config=PowerPointIntegrationConfiguration(),
            naas_integration_config=NaasIntegrationConfiguration(
                api_key=secret.get('NAAS_API_KEY')
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