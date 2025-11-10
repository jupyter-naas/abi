from langchain_openai import ChatOpenAI
from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from src import secret
from pydantic import SecretStr
from src import config

NAME = "Support"
MODEL = "gpt-4.1-mini"
TEMPERATURE = 0
AVATAR_URL = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
DESCRIPTION = "A Support Agent that helps to get any feedbacks/bugs or needs from user."
SYSTEM_PROMPT = f"""
<role>
You are a Support Agent focused on handling user feedbacks.
</role>

<objective>
Gather feedbacks from users and create tickets for support team.
</objective>

<context>
You will receive messages from users.
You are working with the GitHub repository: {config.github_repository}, {config.github_project_id}.
</context>

<tasks>
- Understand user's request
- Create ticket from user's request for support team.
- Provide clear status updates and next steps.
</tasks>

<tools>
- `report_bug`: Create bug reports about issues, errors, crashes etc.
- `feature_request`: Create feature requests about new features or improvements, documentation, etc.
- `github_list_repository_contributors`: List contributors to a repository.
- `github_list_organization_repositories`: List repositories for an organization.
- `githubgraphql_list_priorities`: List priorities for a project.
- `githubgraphql_get_project_node_id`: Get the node ID of a project.
</tools>

<operating_guidelines>
- Identify is the request is feature request or bug report.
- Use the `githubgraphql_list_priorities` tool to get the priority's information and assign the appropriate priority to the ticket. If not specified, assign medium priority.
- Create a draft ticket with:
    - title: based on the request in markdown format.
    - description: based on the request in markdown format.
    - priority: use the `githubgraphql_list_priorities` tool to get the priority's information and assign the appropriate priority to the ticket. If not specified, assign medium priority.
    - assignees (optional): if specified in brief, use the `github_list_repository_contributors` tool to get the contributor's information and add it to the assignee list if it matches a contributor.
    - repository (optional): if specified in brief, use the `github_list_organization_repositories` tool to get the repository's information and assign the appropriate repository to the ticket. If not specified, use the default repository.
    ```
    ### Repository (change if specified in brief)
    {config.github_repository} (default)

    ### Title
    Title of the ticket.
    
    ### Description
    Description of the ticket.

    ### Priority (change if specified in brief)
    Medium (default)
    
    ### Assignees (if specified in brief)
    
    ```
- Validate draft ticket with user and ask for approval.
- Use appropriate tool to create the ticket.
- Report back the URL of the ticket to the user.
</operating_guidelines>

<constraints>
- Be professional and friendly.
- Always ask for approval before creating the ticket.
- Do not ask user for title and description, directly create the draft ticket with the title and description based on the user's request.
- Use tools specificied in your system prompt to end your task successfully.
- Do not use any other tools than the ones specified in your system prompt.
</constraints>
"""

SUGGESTIONS: list[dict[str, str]] = [
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
) -> IntentAgent:
    # Define model
    from src.core.chatgpt.models.gpt_4_1_mini import model

    # Define tools
    tools: list = []
    from src.marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        GitHubGraphqlIntegrationConfiguration,
        as_tools as GitHubGraphqlIntegration_tools,
    )
    from src.marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegrationConfiguration,
        as_tools as GitHubIntegration_tools,
    )
    from src.marketplace.domains.support.workflows.ReportBugWorkflow import (
        ReportBugWorkflow,
        ReportBugWorkflowConfiguration,
    )
    from src.marketplace.domains.support.workflows.FeatureRequestWorkflow import (
        FeatureRequestWorkflow,
        FeatureRequestWorkflowConfiguration,
    )
    github_access_token = secret.get("GITHUB_ACCESS_TOKEN")
    github_integration_config = GitHubIntegrationConfiguration(
        access_token=github_access_token
    )
    github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
        access_token=github_access_token
    )
    tools += [tool for tool in GitHubIntegration_tools(github_integration_config) if tool.name in ["github_list_repository_contributors", "github_list_organization_repositories"]]
    tools += [tool for tool in GitHubGraphqlIntegration_tools(github_graphql_integration_config) if tool.name in ["githubgraphql_list_priorities", "githubgraphql_get_project_node_id"]]

    # Add ReportBugWorkflow tool
    report_bug_workflow = ReportBugWorkflow(
        ReportBugWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        )
    )
    tools += report_bug_workflow.as_tools()

    # Add FeatureRequestWorkflow tool
    feature_request_workflow = FeatureRequestWorkflow(
        FeatureRequestWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        )
    )
    tools += feature_request_workflow.as_tools()
    
    # Define specific intents for support operations
    intents: list = [
        # Bug reporting intents
        Intent(intent_value="I found a bug", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Report a bug", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Something is broken", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Error in the system", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Application crashed", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="System not working", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Integration problem", intent_type=IntentType.TOOL, intent_target="report_bug"),
        
        # Feature request intents
        Intent(intent_value="Feature request", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="I need a new feature", intent_type=IntentType.TOOL, intent_target="feature_request"),
    ]
   
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return SupportAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SupportAgent(IntentAgent):
    pass