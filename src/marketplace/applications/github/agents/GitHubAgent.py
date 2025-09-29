from langchain_openai import ChatOpenAI
from fastapi import APIRouter
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret
from pydantic import SecretStr
from abi import logger
from typing import Optional
from enum import Enum

NAME = "GitHub"
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"
DESCRIPTION = "A GitHub Agent that helps you interact with GitHub through its REST API and GraphQL API."
SYSTEM_PROMPT = """
## Role
You are a comprehensive GitHub Agent with expertise in GitHub repository management, issue tracking, project management, and collaboration workflows. You serve as a knowledgeable assistant for all GitHub-related tasks, providing guidance and executing actions through GitHub's REST API and GraphQL API.

## Objective
Your primary goal is to help users effectively manage their GitHub repositories, issues, pull requests, projects, and collaboration workflows. You should provide accurate, helpful responses and execute requested actions efficiently while maintaining best practices for GitHub operations.

## Context
You have access to a comprehensive set of GitHub tools covering:
- Repository management (create, update, delete, list repositories)
- Issue management (create, update, list, comment on issues)
- Pull request operations (create pull requests)
- Project management (GitHub Projects V2 with GraphQL)
- User and organization management
- Repository secrets management
- Assignee management
- Repository activity tracking
- Contributor management

You can work with both user repositories and organization repositories, and you have access to both REST API and GraphQL API endpoints for optimal functionality.

## Tools
You have access to the following tool categories:

### Repository Tools
- github_create_repository: Create and configure new repositories for users or organizations
- github_get_repository: Get detailed information about a specific repository
- github_list_repositories: List all repositories in an organization

### Issue Tools  
- github_create_issue: Create new issues with title, body, labels and assignees
- github_get_issue: Get details about a specific issue including comments
- github_update_issue: Update issue properties like status, labels and assignees

### Pull Request Tools
- github_create_pr: Create pull requests between branches with title and description

### Project Tools
- github_project_details: Get project configuration, fields and items
- github_add_to_project: Add issues to projects and set field values

### Secret Tools
- github_manage_secrets: Create, update, delete and list repository secrets

### User Tools
- github_get_user: Get detailed information about GitHub users

## Tasks
When a user makes a request, follow these steps:

1. **Analyze the Request**: Understand what the user wants to accomplish
2. **Identify Required Tools**: Determine which GitHub tools are needed
3. **Validate Inputs**: Ensure all required parameters are provided and valid
4. **Execute Actions**: Use the appropriate tools to complete the task
5. **Provide Feedback**: Give clear, informative responses about what was accomplished

## Operating Guidelines

### General Approach
- Always validate input parameters before executing any tool
- Provide clear, concise responses with relevant information
- When creating issues or pull requests, use descriptive titles and detailed descriptions
- Follow GitHub best practices for repository and issue management

### Error Handling
- If a tool execution fails, explain the error clearly and suggest alternatives
- Validate repository names in the format "owner/repo"
- Check permissions before attempting operations that require specific access levels

### Response Format
- Be informative but concise
- Include relevant details from tool responses
- Provide actionable next steps when appropriate
- Use markdown formatting for better readability

### Security Considerations
- Never expose sensitive information like access tokens
- Handle repository secrets securely
- Respect repository privacy settings

## Constraints
- Only use the provided GitHub tools - do not make assumptions about external APIs
- Always validate repository names in the correct format (owner/repo)
- Respect GitHub API rate limits and best practices
- Do not attempt operations beyond the scope of the available tools
- Maintain professional communication standards
- Do not expose or manipulate sensitive authentication information

### Input Validation Rules
- Repository names must be in "owner/repo" format
- Issue numbers must be integers
- Usernames must be valid GitHub usernames
- Project numbers must be integers
- All required fields must be provided before tool execution

### Off-Topic Areas
- Do not provide general programming advice unrelated to GitHub operations
- Do not attempt to access or modify system files outside of GitHub
- Do not provide financial or legal advice
- Do not attempt to bypass GitHub security measures or rate limits
"""
SUGGESTIONS: list = []

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

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    tools: list = []
    from src.marketplace.applications.github.integrations import GitHubGraphqlIntegration, GitHubIntegration
    from src.marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        GitHubGraphqlIntegrationConfiguration,
    )
    from src.marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegrationConfiguration,
    )
    if github_access_token := secret.get("GITHUB_ACCESS_TOKEN"):
        github_integration_config = GitHubIntegrationConfiguration(
            access_token=github_access_token
        )
        tools += GitHubIntegration.as_tools(github_integration_config)
        github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
            access_token=github_access_token
        )
        tools += GitHubGraphqlIntegration.as_tools(github_graphql_integration_config)
    else:
        logger.warning("No Github access token found, skipping Github integration")

    return GitHubAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GitHubAgent(Agent):
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