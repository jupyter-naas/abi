from fastapi import APIRouter
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from src.core.modules.support.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegrationConfiguration,
)
from src.core.modules.support.integrations.GithubIntegration import (
    GithubIntegrationConfiguration,
)
from src.core.modules.support.workflows.GitHubSupportWorkflows import (
    GitHubSupportWorkflows,
    GitHubSupportWorkflowsConfiguration,
)
from typing import Optional
from enum import Enum
from pydantic import SecretStr

NAME = "support_agent"
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
DESCRIPTION = (
    "A Support Assistant that helps to get any feedbacks/bugs or needs from user."
)
SYSTEM_PROMPT = """
You are a support assistant focusing on answering user requests and creating features requests or reporting bugs.

Be sure to follow the chain of thought:
1.1. Identify if the user intent:
  - Feature request: New integration with external API, new ontology pipeline, or new workflow
  - Bug report: Issue with existing integration, pipeline, or workflow

1.2. Use `support_agent_list_issues` tool to check for similar issues. Get more details about the issue using `support_agent_get_details` tool.

1.3.1. If no similar issue, you MUST generate the draft proposition with a title and description based on the user request.
1.3.2. If similar issue, display its details and propose following options to the user:
    - Create new issue (include draft in your response)
    - Update existing issue (include proposed updates in your response)
    - Take no action

1.4. After explicit user approval use appropriate tool to complete your task: "support_agent_create_bug_report" or "support_agent_create_feature_request".

You MUST be sure to validate all input arguments before executing any tool.
Be clear and concise in your responses.
"""
SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: [Feature Request]",
    },
    {
        "label": "Report Bug",
        "value": "Report a bug on: [Bug Description]",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    tools: list = []

    if github_access_token := secret.get("GITHUB_ACCESS_TOKEN"):
        github_integration_config = GithubIntegrationConfiguration(
            access_token=github_access_token
        )
        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(
            access_token=github_access_token
        )

        # Add GetIssuesWorkflow tool
        get_issues_workflow = GitHubSupportWorkflows(
            GitHubSupportWorkflowsConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += get_issues_workflow.as_tools()

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return SupportAssistant(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class SupportAssistant(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize(),
        description: str = "API endpoints to call the Support agent completion.",
        description_stream: str = "API endpoints to call the Support agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )