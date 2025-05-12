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
from src.core.modules.common.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from src.core.modules.common.integrations.LinkedInIntegration import (
    LinkedInIntegrationConfiguration,
)
from src.core.modules.growth.workflows.LinkedinPostsInteractionsWorkflow import (
    LinkedinPostsInteractionsWorkflow,
    LinkedinPostsInteractionsWorkflowConfiguration,
)

NAME = "Growth Assistant"
DESCRIPTION = "Qualifies marketing leads and optimizes sales pipeline through content interaction analysis."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_marketing.png"
)
SYSTEM_PROMPT = f"""You are a growth expert who analyzes content interactions to identify and qualify the most promising marketing leads for sales teams.

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

    # Init secrets
    naas_api_key = secret.get("NAAS_API_KEY")
    li_at = None
    JSESSIONID = None

    # Get LK secrets
    if naas_api_key:
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
        li_at = (
            NaasIntegration(naas_integration_config)
            .get_secret("li_at")
            .get("secret")
            .get("value")
        )
        JSESSIONID = (
            NaasIntegration(naas_integration_config)
            .get_secret("JSESSIONID")
            .get("secret")
            .get("value")
        )

    # Add tools
    if li_at and JSESSIONID:
        linkedin_integration_config = LinkedInIntegrationConfiguration(
            li_at=li_at, JSESSIONID=JSESSIONID
        )
        linkedin_posts_interactions_workflow = LinkedinPostsInteractionsWorkflow(
            LinkedinPostsInteractionsWorkflowConfiguration(
                linkedin_integration_config=linkedin_integration_config
            )
        )
        tools += linkedin_posts_interactions_workflow.as_tools()

    # Add agents
    agents.append(
        create_support_agent(AgentSharedState(thread_id=1), agent_configuration)
    )

    return GrowthAssistant(
        name="growth_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class GrowthAssistant(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = "growth",
        name: str = NAME,
        description: str = "API endpoints to call the Growth assistant completion.",
        description_stream: str = "API endpoints to call the Growth assistant stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
