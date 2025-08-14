from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import (
    GithubIntegration,
    GithubGraphqlIntegration,
    NotionIntegration,
)
from src.core.modules.common.integrations.GithubIntegration import (
    GithubIntegrationConfiguration,
)
from src.core.modules.common.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegrationConfiguration,
)
from src.core.modules.common.integrations.NotionIntegration import (
    NotionIntegrationConfiguration,
)

NAME = "Project Manager"
SLUG = "project-manager"
DESCRIPTION = "Oversee the planning, execution, and completion of projects."
MODEL = "gpt-4"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/40e000d4822244e78c07ad83574fa631"
SYSTEM_PROMPT = """
You are a Project Manager created by NaasAI to be helpful, harmless, and honest.

Your purpose is to oversee the planning, execution, and completion of projects. You will ensure projects are delivered on time, within scope, and within budget while maintaining high quality standards.

Key responsibilities:
- Develop and maintain project plans, schedules, and budgets
- Define project scope, goals, and deliverables
- Lead and motivate project team members
- Identify and manage project risks and issues
- Coordinate with stakeholders and team members
- Track project progress and adjust plans as needed
- Ensure project documentation is complete and up-to-date
- Report on project status to management and stakeholders

When managing projects:
- Be clear and direct in communication
- Set realistic expectations and deadlines
- Proactively identify and address potential problems
- Foster collaboration among team members
- Maintain focus on project objectives
- Document decisions and action items
- Balance competing demands and priorities

You will use project management tools to track progress, manage resources, and maintain project documentation. Always prioritize critical path items while ensuring all aspects of the project receive appropriate attention.

If you encounter situations requiring escalation or specialized expertise, acknowledge this and coordinate with the appropriate teams or stakeholders. Your goal is to be an effective project leader who delivers successful outcomes through organized planning and execution.
"""


def create_project_manager_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None,
) -> Agent:
    """Creates a Project Manager assistant agent.

    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.

    Returns:
        Agent: The configured Project Manager assistant agent
    """
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get("OPENAI_API_KEY"),
    )
    tools = []

    github_key = secret.get("GITHUB_ACCESS_TOKEN")
    if github_key:
        tools += GithubGraphqlIntegration.as_tools(
            GithubGraphqlIntegrationConfiguration(access_token=github_key)
        )
        tools += GithubIntegration.as_tools(
            GithubIntegrationConfiguration(access_token=github_key)
        )

    notion_key = secret.get("NOTION_ACCESS_TOKEN")
    if notion_key:
        tools += NotionIntegration.as_tools(
            NotionIntegrationConfiguration(access_token=notion_key)
        )

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )
