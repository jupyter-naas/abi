from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from fastapi import APIRouter
from src.core.modules.support.agents.SupportAssistant import (
    create_agent as create_support_agent,
)
from src.core.modules.common.prompts.responsabilities_prompt import (
    RESPONSIBILITIES_PROMPT,
)
from src.core.modules.common.integrations.HubSpotIntegration import (
    HubSpotIntegrationConfiguration,
)
from src.core.modules.sales.workflows.HubSpotWorkflows import (
    HubSpotWorkflows,
    HubSpotWorkflowsConfiguration,
)

NAME = "Sales Assistant"
DESCRIPTION = "Qualifies leads and manages customer relationships through CRM and billing systems."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/sales_conversion.png"
)
SYSTEM_PROMPT = f"""You are a sales expert focused on maximizing revenue by qualifying leads and optimizing the sales pipeline.
You leverage CRM data and billing systems to manage contacts, prepare demos, and create customized offers.

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""
SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: [Feature Request]",
    },
    {"label": "Report Bug", "value": "Report a bug on: [Bug Description]"},
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
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Add tools
    hubspot_access_token = secret.get("HUBSPOT_ACCESS_TOKEN")
    if hubspot_access_token:
        hubspot_integration_config = HubSpotIntegrationConfiguration(
            access_token=hubspot_access_token
        )
        hubspot_workflows = HubSpotWorkflows(
            HubSpotWorkflowsConfiguration(
                hubspot_integration_config=hubspot_integration_config
            )
        )
        tools += hubspot_workflows.as_tools()

    # Add agents
    agents.append(
        create_support_agent(AgentSharedState(thread_id=1), agent_configuration)
    )

    return SalesAssistant(
        name="sales_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class SalesAssistant(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = "sales",
        name: str = NAME,
        description: str = "API endpoints to call the Sales assistant completion.",
        description_stream: str = "API endpoints to call the Sales assistant stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
