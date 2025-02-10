from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from abi import logger
from fastapi import APIRouter
from src.core.assistants.domain.OpenDataAssistant import create_open_data_assistant
from src.core.assistants.domain.ContentAssistant import create_content_assistant
from src.core.assistants.domain.GrowthAssistant import create_growth_assistant
from src.core.assistants.domain.SalesAssistant import create_sales_assistant
from src.core.assistants.domain.OperationsAssistant import create_operations_assistant
from src.core.assistants.domain.FinanceAssistant import create_finance_assistant 
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "A Supervisor Assistant that helps to supervise the other domain assistants."
SUPERVISOR_AGENT_INSTRUCTIONS = f"""
You are ABI a super-assistant.
Present yourself as a super-assistant and by listing all the assistants you have access to.

ASSISTANTS
----------
For assistants tools, make sure to validate input arguments mandatory fields (not optional) with the user in human readable terms according to the provided schema before proceeding.
You have access to the following assistants:
[ASSISTANTS]

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""

def create_supervisor_assistant(
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
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=1)

    # Add agents
    agents = [
        create_open_data_assistant(AgentSharedState(thread_id=2), agent_configuration),
        create_content_assistant(AgentSharedState(thread_id=3), agent_configuration),
        create_growth_assistant(AgentSharedState(thread_id=4), agent_configuration),
        create_sales_assistant(AgentSharedState(thread_id=5), agent_configuration),
        create_operations_assistant(AgentSharedState(thread_id=6), agent_configuration),
        create_finance_assistant(AgentSharedState(thread_id=7), agent_configuration),
        create_support_assistant(AgentSharedState(thread_id=8), agent_configuration)
    ]

    # Get tools info from each assistant
    assistants_info = []
    for assistant in agents[:-1]:  # Exclude support assistant
        assistant_info = {
            "name": assistant.name,
            "description": assistant.description,
            "tools": [
                {"name": t.name, "description": t.description}
                for t in assistant.tools  # Access the private tools attribute
            ]
        }        
        assistants_info.append(assistant_info)

    # Transform assistants_info into formatted string
    assistants_info_str = ""
    for assistant in assistants_info:
        assistants_info_str += f"-{assistant['name']}: {assistant['description']}\n"
        for tool in assistant['tools']:
            assistants_info_str += f"   • {tool['name']}: {tool['description']}\n"
        assistants_info_str += "\n"

    # Replace the {{ASSISTANTS}} placeholder in the system prompt with the assistants_info
    agent_configuration.system_prompt=SUPERVISOR_AGENT_INSTRUCTIONS.replace("[ASSISTANTS]", assistants_info_str)

    return SupervisorAssistant(
        name="supervisor_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents, # Agents will be loaded as tools.
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    )

class SupervisorAssistant(Agent):
    def as_api(
            self, 
            router: APIRouter, 
            route_name: str = "supervisor", 
            name: str = "Supervisor Assistant", 
            description: str = "API endpoints to call the Supervisor assistant completion.", 
            description_stream: str = "API endpoints to call the Supervisor assistant stream completion.",
            tags: list[str] = []
        ):
        return super().as_api(router, route_name, name, description, description_stream, tags)