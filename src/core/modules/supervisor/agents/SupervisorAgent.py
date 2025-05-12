from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from langchain_openai import ChatOpenAI
from src import secret
from src.core.modules.ontology.agents.OntologyAgent import (
    create_agent as create_ontology_agent,
)
from src.core.modules.naas.agents.NaasAgent import (
    create_agent as create_naas_agent,
)
from src.core.modules.support.agents.SupportAgent import (
    create_agent as create_support_agent,
)

NAME = "supervisor"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = f"""You are ABI, an advanced orchestrator agent designed to coordinate multiple specialized agents.

General Rules
--------------------------------
- You MUST always include the agent and tool used at the beginning of the report in human readable format as follow: '> {{Agent Name}} - {{Tool Name}}' + 2 blank lines (e.g. '> Ontology Agent - Search Class\n\n' for agent: ontology_agent, tool: ontology_search_class)
- If you can't delegate the task, you can create a feature request using the 'support_agent_create_feature_request' tool. You MUST validate the need of the user request before creating a feature request. Return the issue html URL in the response.
- If an error occurs, you MUST use the 'support_agent_create_bug_report' tool to create a bug report. Return the issue html URL in the response.
- Return URL links as follow: [Link](https://www.google.com)
- Return Images as follow: ![Image](https://www.google.com/image.png)
- You MUST always adapt your language to the user request. If user request is written in french, you MUST answer in french.
"""

SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: {{Feature Request}}",
    },
    {
        "label": "Report Bug", 
        "value": "Report a bug on: {{Bug Description}}",
    },    
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
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=secret.get("OPENAI_API_KEY")
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
            on_tool_usage=lambda x: print(x),
            on_tool_response=lambda x: print(x),
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Add support agents
    agents = [
        create_support_agent(),
        create_ontology_agent(),
        create_naas_agent(),
    ]

    return SupervisorAgent(
        name=NAME,
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
        route_name: str = NAME,
        name: str = NAME.capitalize(),
        description: str = "API endpoints to call the Supervisor agent completion.",
        description_stream: str = "API endpoints to call the Supervisor agent stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
