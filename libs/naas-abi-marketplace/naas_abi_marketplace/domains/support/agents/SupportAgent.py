from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.domains.support import ABIModule

NAME = "Support"
AVATAR_URL = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
DESCRIPTION = "Get user feedbacks to create tickets for support team in GitHub."
SYSTEM_PROMPT = """<role>
You are a Support Agent focused on handling user feedbacks.
</role>

<objective>
Gather feedbacks from users and create tickets for support team.
</objective>

<context>
You will receive messages from users.
You are working with the GitHub repository: [GITHUB_REPOSITORY], [GITHUB_PROJECT_ID].
</context>

<tasks>
- Understand user's request
- Create ticket from user's request for support team.
- Provide clear status updates and next steps.
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Identify is the request is feature request or bug report.
- Use the `githubgraphql_list_priorities` tool to get the priority's information and assign the appropriate priority to the ticket. If not specified, assign medium priority.
- Create a draft ticket with:
    - title: based on the request in markdown format.
    - description: based on the request in markdown format.
    - priority: use the `githubgraphql_list_priorities` tool to get the priority's information and assign the appropriate priority to the ticket. If not specified, assign medium priority.
    - assignees (): if specified in brief, use the `github_list_repository_contributors` tool to get the contributor's information and add it to the assignee list if it matches a contributor.
    - repository (): if specified in brief, use the `github_list_organization_repositories` tool to get the repository's information and assign the appropriate repository to the ticket. If not specified, use the default repository.
    ```
    ### Repository (change if specified in brief)
    [GITHUB_REPOSITORY] (default)

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
    # Initialize module
    module = ABIModule.get_instance()
    github_project_id = module.configuration.github_project_id
    default_repository = module.configuration.default_repository
    github_access_token = module.configuration.github_access_token

    # Define model
    from naas_abi_marketplace.domains.support.models.default import get_model
    model = get_model()

    # Define tools
    tools: list = []
    from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        GitHubGraphqlIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        as_tools as GitHubGraphqlIntegration_tools,
    )
    from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
        as_tools as GitHubIntegration_tools,
    )
    from naas_abi_marketplace.domains.support.workflows.FeatureRequestWorkflow import (
        FeatureRequestWorkflow,
        FeatureRequestWorkflowConfiguration,
    )
    from naas_abi_marketplace.domains.support.workflows.ReportBugWorkflow import (
        ReportBugWorkflow,
        ReportBugWorkflowConfiguration,
    )
    github_integration_config = GitHubIntegrationConfiguration(
        access_token=github_access_token
    )
    github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
        access_token=github_access_token
    )
    tools += [
        tool
        for tool in GitHubIntegration_tools(github_integration_config)
        if tool.name
        in [
            "github_list_repository_contributors",
            "github_list_organization_repositories",
        ]
    ]
    tools += [
        tool
        for tool in GitHubGraphqlIntegration_tools(github_graphql_integration_config)
        if tool.name
        in ["githubgraphql_list_priorities", "githubgraphql_get_project_node_id"]
    ]

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
        Intent(
            intent_value="I found a bug",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        Intent(
            intent_value="Report a bug",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        Intent(
            intent_value="Something is broken",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        Intent(
            intent_value="Error in the system",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        Intent(
            intent_value="Application crashed",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        Intent(
            intent_value="System not working",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        Intent(
            intent_value="Integration problem",
            intent_type=IntentType.TOOL,
            intent_target="report_bug",
        ),
        # Feature request intents
        Intent(
            intent_value="Feature request",
            intent_type=IntentType.TOOL,
            intent_target="feature_request",
        ),
        Intent(
            intent_value="I need a new feature",
            intent_type=IntentType.TOOL,
            intent_target="feature_request",
        ),
        Intent(
            intent_value="I want to suggest a new feature",
            intent_type=IntentType.TOOL,
            intent_target="feature_request",
        ),
    ]

    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    system_prompt = system_prompt.replace(
        "[GITHUB_PROJECT_ID]", str(github_project_id)
    )
    system_prompt = system_prompt.replace(
        "[GITHUB_REPOSITORY]", default_repository
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)

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
