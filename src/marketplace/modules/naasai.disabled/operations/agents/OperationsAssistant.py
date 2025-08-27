from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret, services
from fastapi import APIRouter
from src.core.modules.support.agents.SupportAssistant import (
    create_agent as create_support_agent,
)
from src.core.modules.common.prompts.responsabilities_prompt import (
    RESPONSIBILITIES_PROMPT,
)
from src.core.modules.common.integrations import AiaIntegration
from src.core.modules.common.integrations.AiaIntegration import (
    AiaIntegrationConfiguration,
)
from src.core.modules.common.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from src.core.modules.common.integrations.GithubIntegration import (
    GithubIntegrationConfiguration,
)
from src.core.modules.common.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegrationConfiguration,
)
from src.core.modules.operations.workflows.CreateIssueAndAddToProjectWorkflow import (
    CreateIssueAndAddToProjectWorkflow,
    CreateIssueAndAddToProjectWorkflowConfiguration,
)
from src.core.modules.operations.workflows.GetTopPrioritiesWorkflow import (
    GetTopPrioritiesWorkflow,
    GetTopPrioritiesConfiguration,
)
from src.core.modules.operations.workflows.AssignIssuesToProjectWorkflow import (
    AssignIssuesToProjectWorkflow,
    AssignIssuesToProjectWorkflowConfiguration,
)
from src.core.modules.operations.pipelines.github.GithubIssuesPipeline import (
    GithubIssuesPipeline,
    GithubIssuesPipelineConfiguration,
)
from src.core.modules.operations.pipelines.github.GithubUserDetailsPipeline import (
    GithubUserDetailsPipeline,
    GithubUserDetailsPipelineConfiguration,
)
from src.core.modules.operations.workflows.NaasWorkspaceWorkflows import (
    NaasWorkspaceWorkflows,
    NaasWorkspaceWorkflowsConfiguration,
)

NAME = "Operations Assistant"
DESCRIPTION = "Optimizes workflows and automates project management tasks to maximize operational efficiency."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/operations_efficiency.png"
SYSTEM_PROMPT = f"""You are a workflow optimization expert focused on streamlining operations and project management.
Your primary goal is to help users automate tasks and improve operational efficiency.

RESPONSIBILITIES
----------------
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

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Init secrets
    naas_api_key = secret.get("NAAS_API_KEY")
    github_access_token = secret.get("GITHUB_ACCESS_TOKEN")
    li_at = None
    JSESSIONID = None

    # Init ontology store
    triple_store = services.triple_store_service

    # Add integrations & workflbased on available credentials
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

        # Add NaasWorkspaceWorkflow tool
        naas_workspace_workflows = NaasWorkspaceWorkflows(
            NaasWorkspaceWorkflowsConfiguration(
                naas_integration_config=naas_integration_config
            )
        )
        tools += naas_workspace_workflows.as_tools()

    if naas_api_key and li_at and JSESSIONID:
        aia_integration_config = AiaIntegrationConfiguration(
            api_key=naas_api_key, li_at=li_at, JSESSIONID=JSESSIONID
        )
        tools += AiaIntegration.as_tools(aia_integration_config)

    if github_access_token:
        github_integration_config = GithubIntegrationConfiguration(
            access_token=github_access_token
        )
        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(
            access_token=github_access_token
        )

        # Add CreateIssueAndAddToProjectWorkflow tool
        create_issue_and_add_to_project_workflow = CreateIssueAndAddToProjectWorkflow(
            CreateIssueAndAddToProjectWorkflowConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += create_issue_and_add_to_project_workflow.as_tools()

        # Add AssignIssuesToProjectWorkflow tool
        assign_issues_to_project_workflow = AssignIssuesToProjectWorkflow(
            AssignIssuesToProjectWorkflowConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += assign_issues_to_project_workflow.as_tools()

        # Add GithubIssuesPipeline tool
        github_issues_pipeline = GithubIssuesPipeline(
            GithubIssuesPipelineConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
                triple_store=triple_store,
            )
        )
        tools += github_issues_pipeline.as_tools()

        # Add GithubUserDetailsPipeline tool
        github_user_details_pipeline = GithubUserDetailsPipeline(
            GithubUserDetailsPipelineConfiguration(
                github_integration_config=github_integration_config,
                triple_store=triple_store,
            )
        )
        tools += github_user_details_pipeline.as_tools()

    if triple_store:
        # Add GetTopPrioritiesWorkflow tool
        get_top_priorities_workflow = GetTopPrioritiesWorkflow(
            GetTopPrioritiesConfiguration(triple_store=triple_store)
        )
        tools += get_top_priorities_workflow.as_tools()

    # Add agents
    agents.append(
        create_support_agent(AgentSharedState(thread_id=1), agent_configuration)
    )

    return OperationsAssistant(
        name="operations_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class OperationsAssistant(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = "operations",
        name: str = NAME,
        description: str = "API endpoints to call the Operations assistant completion.",
        description_stream: str = "API endpoints to call the Operations assistant stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
