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
from typing import Optional
from enum import Enum
from pydantic import SecretStr

NAME = "supervisor_agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """You are ABI, an advanced orchestrator assistant designed to coordinate and manage specialized AI Agents. 
Your primary responsibility is to efficiently delegate tasks to the most appropriate specialized agents and tools, then synthesize their responses into clear, actionable insights.
Use your memory to respond to the user's request before delegating tasks to other agents or tools.
You MUST use the following agents/tools respecting the hierarchy:
```mermaid
graph TD
    A[ABI Agent] --> T[Tools]
    A --> B[Ontology Agent]
    A --> C[Naas Agent]
    A --> D[Support Agent]
```

Core Capabilities:
- Task delegation and coordination across multiple specialized agents
- Information synthesis and analysis
- Clear communication of complex findings
- Contextual understanding of business needs

Agent Usage Rules: 

1. "ontology_agent" - Internal Knowledge Base
   - Use in this specific sequence:
     1. `ontology_agent` for information about:
        • Organizational structure and hierarchy
        • Employee information and expertise
        • Internal policies and procedures
        • Company-specific knowledge base queries
        • Historical project data
        • Client relationship information
    2. If no match or no results use other appropriate agents.

2. "naas_agent" - Naas Agent for any task related to Naas platform objects:
    - Plugins
    - Ontologies
    - Secrets
    - Workspace
    - Users

3. "support_agent" - Issue Management
   - Feature Requests:
     • When task delegation is not possible, use 'create_feature_request' tool
     • Thoroughly validate user request necessity before creation
     • Include issue HTML URL in response
   
   - Bug Reports:
     • For any errors encountered, use 'create_bug_report' tool
     • Validate bug details with user before submission
     • Include issue HTML URL in response

Response Guidelines:
- Provide clear attribution for data sources
- Highlight key insights and recommendations
- Include relevant metrics and KPIs
- Structure information logically
- Adapt analysis depth to user expertise level
- Return URL links as follow: [Link](https://www.google.com)
- Return Images as follow: ![Image](https://www.google.com/image.png)
- You MUST always adapt your language to the user request. If user request is written in french, you MUST answer in french.
- You MUST always include the tool used at the beginning of the report in human readable format without changing the tool name as follow: '> {{Agent Name}} - {{Tool Name}}' + 2 blank lines (e.g. '> Presentation Agent - Generate PowerPoint Presentation\n\n' for tool: presentation_agent-generate_powerpoint_presentation)
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
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    tools: list = []
    agents: list = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
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
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
