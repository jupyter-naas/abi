from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from langchain_openai import ChatOpenAI
from src import secret
from src.core.modules.support.agents.SupportAgent import (
    create_agent as create_support_agent,
)

NAME = "Supervisor Agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """You are ABI, an advanced orchestrator agent designed to coordinate multiple specialized agents.

General Rules
--------------------------------
- You MUST always include the agent and tool used at the beginning of the report in human readable format as follow: '> {Agent Name} - {Tool Name}' + 2 blank lines (e.g. '> Ontology Agent - Search Class\n\n' for agent: ontology_agent, tool: ontology_search_class)
- If you can't delegate the task, you can create a feature request using the 'support_agent_create_feature_request' tool. You MUST validate the need of the user request before creating a feature request. Return the issue html URL in the response.
- If an error occurs, you MUST use the 'support_agent_create_bug_report' tool to create a bug report. Return the issue html URL in the response.
- Return URL links as follow: [Link](https://www.google.com)
- Return Images as follow: ![Image](https://www.google.com/image.png)
- You MUST always adapt your language to the user request. If user request is written in french, you MUST answer in french.

Agents
--------------------------------
[AGENTS]
"""

SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: {{Feature Request}}",
    },
    {"label": "Report Bug", "value": "Report a bug on: {{Bug Description}}"},
]


def create_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, temperature=TEMPERATURE, api_key=secret.get("OPENAI_API_KEY")
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration()
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=1)

    # Add support agent
    github_api_token = secret.get("GITHUB_ACCESS_TOKEN")
    if github_api_token is not None:
        support_agent = create_support_agent(
            AgentSharedState(thread_id=2), agent_configuration
        )
        agents.append(support_agent)

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
            ],
        }
        agents_info.append(agent_info)

    # Transform agents_info into formatted string
    agents_info_str = ""
    for agent in agents_info:
        agents_info_str += f"-{agent['name']}: {agent['description']}\n"
        for tool in agent["tools"]:
            agents_info_str += f"   • {tool['name']}: {tool['description']}\n"
        agents_info_str += "\n"

    # Replace the [AGENTS] placeholder in the system prompt with the agents_info
    system_prompt = SYSTEM_PROMPT.replace("[AGENTS]", agents_info_str)
    agent_configuration.system_prompt = system_prompt

    return SupervisorAgent(
        name="supervisor_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class SupervisorAgent(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = "supervisor",
        name: str = NAME,
        description: str = "API endpoints to call the Supervisor agent completion.",
        description_stream: str = "API endpoints to call the Supervisor agent stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
