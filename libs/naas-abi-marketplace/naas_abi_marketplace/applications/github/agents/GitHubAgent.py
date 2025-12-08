from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.github import ABIModule

NAME = "GitHub"
AVATAR_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"
DESCRIPTION = "Helps you interact with GitHub through its REST API and GraphQL API."
SYSTEM_PROMPT = """<role>
You are a GitHub Agent with expertise in repository management, issue tracking, project management, and collaboration workflows.
</role>

<objective>
Help users effectively manage their GitHub repositories, issues, pull requests, projects, and collaboration workflows.
</objective>

<context>
You have access to GitHub tools for GitHub operations.
</context>

<tasks>
- Analyze user requests and identify required GitHub operations
- Validate input parameters before executing any tool
- Execute GitHub operations using appropriate tools
- Provide clear, informative responses about completed actions
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Validate that all required parameters are provided and valid before using tool.
- Use descriptive titles and detailed descriptions when creating issues or pull requests
- Provide clear, concise responses with relevant information from tool responses
</operating_guidelines>

<constraints>
- Only use the provided GitHub tools - do not make assumptions about external APIs
- Do not attempt operations beyond the scope of the available tools
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()
    github_access_token = module.configuration.github_access_token

    # Define model
    from naas_abi_marketplace.applications.github.models.default import get_model
    model = get_model()

    # Define tools
    tools: list = []
    from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        GitHubGraphqlIntegrationConfiguration,
        as_tools as GitHubGraphqlIntegration_tools,
    )
    from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegrationConfiguration,
        as_tools as GitHubIntegration_tools,
    )
    github_integration_config = GitHubIntegrationConfiguration(
        access_token=github_access_token
    )
    tools += GitHubIntegration_tools(github_integration_config)
    github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
        access_token=github_access_token
    )
    tools += GitHubGraphqlIntegration_tools(github_graphql_integration_config)

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get details about a GitHub user",
            intent_type=IntentType.TOOL,
            intent_target="github_get_user_details"
        ),
        Intent(
            intent_value="Create a new repository for the user",
            intent_type=IntentType.TOOL,
            intent_target="github_create_user_repository"
        ),
        Intent(
            intent_value="Get details about a GitHub repository",
            intent_type=IntentType.TOOL,
            intent_target="github_get_repository_details"
        ),
        Intent(
            intent_value="List repositories for the specified organization in GitHub",
            intent_type=IntentType.TOOL,
            intent_target="github_list_organization_repositories"
        ),
        Intent(
            intent_value="Create a new repository for an organization",
            intent_type=IntentType.TOOL,
            intent_target="github_create_organization_repository"
        ),
        Intent(
            intent_value="Update a repository for an organization",
            intent_type=IntentType.TOOL,
            intent_target="github_update_organization_repository"
        ),
        Intent(
            intent_value="Delete a repository for an organization",
            intent_type=IntentType.TOOL,
            intent_target="github_delete_organization_repository"
        ),
        Intent(
            intent_value="Get a list of activities for the specified repository",
            intent_type=IntentType.TOOL,
            intent_target="github_list_repository_activities"
        ),
        Intent(
            intent_value="Get a list of contributors for the specified repository",
            intent_type=IntentType.TOOL,
            intent_target="github_get_repository_contributors"
        ),
        Intent(
            intent_value="Create an issue in the specified repository",
            intent_type=IntentType.TOOL,
            intent_target="github_create_issue"
        ),
        Intent(
            intent_value="Get an issue from a repository",
            intent_type=IntentType.TOOL,
            intent_target="github_get_issue"
        ),
        Intent(
            intent_value="Get issues from a repository",
            intent_type=IntentType.TOOL,
            intent_target="github_list_issues"
        ),
        Intent(
            intent_value="Get comments on an issue or pull request",
            intent_type=IntentType.TOOL,
            intent_target="github_list_issue_comments"
        ),
        Intent(
            intent_value="Get a comment on an issue or pull request",
            intent_type=IntentType.TOOL,
            intent_target="github_get_issue_comment"
        ),
        Intent(
            intent_value="Update a comment on an issue or pull request",
            intent_type=IntentType.TOOL,
            intent_target="github_update_issue_comment"
        ),
        Intent(
            intent_value="Delete a comment on an issue or pull request",
            intent_type=IntentType.TOOL,
            intent_target="github_delete_issue_comment"
        ),
        Intent(
            intent_value="Create a comment on an issue or pull request",
            intent_type=IntentType.TOOL,
            intent_target="github_create_issue_comment"
        ),
        Intent(
            intent_value="Create a pull request in the specified repository",
            intent_type=IntentType.TOOL,
            intent_target="github_create_pull_request"
        ),
        Intent(
            intent_value="Get a list of assignees for the specified repository",
            intent_type=IntentType.TOOL,
            intent_target="github_list_assignees"
        ),
        Intent(
            intent_value="Check if a user can be assigned to a specific issue",
            intent_type=IntentType.TOOL,
            intent_target="github_check_assignee_permission"
        ),
        Intent(
            intent_value="Add assignees to an issue",
            intent_type=IntentType.TOOL,
            intent_target="github_add_assignees_to_issue"
        ),
        Intent(
            intent_value="Remove assignees from an issue",
            intent_type=IntentType.TOOL,
            intent_target="github_remove_assignees_from_issue"
        ),
        Intent(
            intent_value="List all secrets available in a GitHub repository without revealing their encrypted values",
            intent_type=IntentType.TOOL,
            intent_target="github_list_repository_secrets"
        ),
        Intent(
            intent_value="Get a secret from a GitHub repository",
            intent_type=IntentType.TOOL,
            intent_target="github_get_repository_secret"
        ),
        Intent(
            intent_value="Create or update a secret in a GitHub repository",
            intent_type=IntentType.TOOL,
            intent_target="github_create_or_update_repository_secret"
        ),
        Intent(
            intent_value="Delete a secret from a GitHub repository",
            intent_type=IntentType.TOOL,
            intent_target="github_delete_repository_secret"
        ),
        Intent(
            intent_value="List contributors to a GitHub repository",
            intent_type=IntentType.TOOL,
            intent_target="github_list_repository_contributors"
        ),
    ]
    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return GitHubAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GitHubAgent(IntentAgent):
    pass