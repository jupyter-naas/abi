from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from abi import logger
from fastapi import APIRouter
from src.core.assistants.domain.OpenDataAssistant import create_open_data_agent
from src.core.assistants.domain.ContentAssistant import create_content_agent
from src.core.assistants.domain.GrowthAssistant import create_growth_agent
from src.core.assistants.domain.SalesAssistant import create_sales_agent
from src.core.assistants.domain.OperationsAssistant import create_operations_agent
from src.core.assistants.domain.FinanceAssistant import create_finance_agent 
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

NAME = "Supervisor Assistant"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "Coordinates and manages specialized domain agents. It provides seamless access to various business functions including open data, content, growth, sales, operations, finance, and support services."
SYSTEM_PROMPT = f"""You are ABI, an advanced orchestrator assistant designed to coordinate multiple specialized agents.
Your primary role is to understand user requests and direct them to the most appropriate specialized agent.
While you can't offer professional advice or make specific recommendations, you excel at coordinating agents to help users.

When users inquire about your capabilities, provide a clear, structured overview of all available agents
and their tools, organized by domain and function.

RESPONSIBILITIES
----------------
{RESPONSIBILITIES_PROMPT}

AGENTS
------
[AGENTS]
"""

SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: [Feature Request]"
    },
    {
        "label": "Report Bug",
        "value": "Report a bug on: [Bug Description]"
    }
]
def create_supervisor_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []
    system_prompt = SYSTEM_PROMPT # Create a local copy of the system prompt

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE, 
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
        create_open_data_agent(AgentSharedState(thread_id=2), agent_configuration),
        create_content_agent(AgentSharedState(thread_id=3), agent_configuration),
        create_growth_agent(AgentSharedState(thread_id=4), agent_configuration),
        create_sales_agent(AgentSharedState(thread_id=5), agent_configuration),
        create_operations_agent(AgentSharedState(thread_id=6), agent_configuration),
        create_finance_agent(AgentSharedState(thread_id=7), agent_configuration),
        create_support_agent(AgentSharedState(thread_id=8), agent_configuration)
    ]

    # Get tools info from each assistant
    agents_info = []
    for agent in agents: 
        agent_info = {
            "name": agent.name,
            "description": agent.description,
            "tools": [
                {"name": t.name, "description": t.description}
                for t in agent.tools  # Access the private tools attribute
                if t.name != "support_agent" and t.name != "get_current_datetime"
            ]
        }
        agents_info.append(agent_info)

    # Transform assistants_info into formatted string
    agents_info_str = ""
    for agent in agents_info:
        agents_info_str += f"-{agent['name']}: {agent['description']}\n"
        for tool in agent['tools']:
            agents_info_str += f"   • {tool['name']}: {tool['description']}\n"
        agents_info_str += "\n"

    # Replace the [AGENTS] placeholder in the system prompt with the agents_info
    system_prompt = system_prompt.replace("[AGENTS]", agents_info_str)
    agent_configuration.system_prompt = system_prompt

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
        name: str = NAME, 
        description: str = "API endpoints to call the Supervisor assistant completion.", 
        description_stream: str = "API endpoints to call the Supervisor assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)