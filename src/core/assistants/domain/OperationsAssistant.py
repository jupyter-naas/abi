from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config
from fastapi import APIRouter
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import AiaIntegration, NaasIntegration, GithubIntegration, GithubGraphqlIntegration, AlgoliaIntegration
from src.core.integrations.AiaIntegration import AiaIntegrationConfiguration
from src.core.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.core.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.core.integrations.AlgoliaIntegration import AlgoliaIntegrationConfiguration
from src.core.workflows.operations.CreateIssueAndAddToProjectWorkflow import CreateIssueAndAddToProjectWorkflow, CreateIssueAndAddToProjectWorkflowConfiguration
from src.core.workflows.operations.GetTopPrioritiesWorkflow import GetTopPrioritiesWorkflow, GetTopPrioritiesConfiguration
from src.core.workflows.operations.AssignIssuesToProjectWorkflow import AssignIssuesToProjectWorkflow, AssignIssuesToProjectWorkflowConfiguration
from src.core.workflows.operations.AddAssistantsToNaasWorkspaceWorkflow import AddAssistantsToNaasWorkspace, AddAssistantsToNaasWorkspaceConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.core.pipelines.github.GithubIssuesPipeline import GithubIssuesPipeline, GithubIssuesPipelineConfiguration
from src.core.pipelines.github.GithubUserDetailsPipeline import GithubUserDetailsPipeline, GithubUserDetailsPipelineConfiguration
from src.core.workflows.operations.NaasStorageWorkflows import NaasStorageWorkflows, NaasStorageWorkflowsConfiguration
from src.core.workflows.operations.NaasWorkspaceWorkflows import NaasWorkspaceWorkflows, NaasWorkspaceWorkflowsConfiguration
from src.core.workflows.operations.SetupGithubABIWorkflows import SetupGithubABIWorkflows, SetupGithubABIWorkflowsConfiguration

DESCRIPTION = "An Operations Assistant that manages tasks and projects to improve operational efficiency."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/operations_efficiency.png"
SYSTEM_PROMPT = f'''
You are an Operations Assistant.
Your primary role is to enhance operational efficiency.

Please use your tools to perform operations.
Make sure to validate all required input arguments you will use in the tool.

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
'''

def create_operations_assistant(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Add ontology store
    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))

    # Add integrations & workflbased on available credentials
    if naas_key := secret.get('NAAS_API_KEY'):
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_key)

        # Add NaasWorkspaceWorkflow tool
        naas_workspace_workflows = NaasWorkspaceWorkflows(NaasWorkspaceWorkflowsConfiguration(
            naas_integration_config=naas_integration_config
        ))
        tools += naas_workspace_workflows.as_tools()

        # Add AddAssistantsToNaasWorkspace tool
        add_assistants_to_naas_workspace = AddAssistantsToNaasWorkspace(AddAssistantsToNaasWorkspaceConfiguration(
            naas_integration_config=naas_integration_config
        ))
        tools += add_assistants_to_naas_workspace.as_tools()

        # Add NaasStorageWorkflows tool
        naas_storage_workflows = NaasStorageWorkflows(NaasStorageWorkflowsConfiguration(
            naas_integration_config=naas_integration_config
        ))
        tools += naas_storage_workflows.as_tools()

    if (naas_key := secret.get('NAAS_API_KEY')) and (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        aia_integration_config = AiaIntegrationConfiguration(api_key=naas_key)
        tools += AiaIntegration.as_tools(aia_integration_config)

    if github_access_token := secret.get('GITHUB_ACCESS_TOKEN'):
        github_integration_config = GithubIntegrationConfiguration(access_token=github_access_token)
        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=github_access_token)

        # Add SetupGithubABIWorkflows tool
        setup_github_abi_workflows = SetupGithubABIWorkflows(SetupGithubABIWorkflowsConfiguration(
            github_integration_config=github_integration_config
        ))
        tools += setup_github_abi_workflows.as_tools()

        # Add CreateIssueAndAddToProjectWorkflow tool
        create_issue_and_add_to_project_workflow = CreateIssueAndAddToProjectWorkflow(CreateIssueAndAddToProjectWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        ))
        tools += create_issue_and_add_to_project_workflow.as_tools()

        # Add AssignIssuesToProjectWorkflow tool
        assign_issues_to_project_workflow = AssignIssuesToProjectWorkflow(AssignIssuesToProjectWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        ))
        tools += assign_issues_to_project_workflow.as_tools()

        # Add GithubIssuesPipeline tool
        github_issues_pipeline = GithubIssuesPipeline(GithubIssuesPipelineConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
            ontology_store=ontology_store
        ))
        tools += github_issues_pipeline.as_tools()

        # Add GithubUserDetailsPipeline tool
        github_user_details_pipeline = GithubUserDetailsPipeline(GithubUserDetailsPipelineConfiguration(
            github_integration_config=github_integration_config,
            ontology_store=ontology_store
        ))
        tools += github_user_details_pipeline.as_tools()

    # Add GetTopPrioritiesWorkflow tool
    get_top_priorities_workflow = GetTopPrioritiesWorkflow(GetTopPrioritiesConfiguration(
        ontology_store=ontology_store
    ))
    tools += get_top_priorities_workflow.as_tools()
    
    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=1), agent_configuration))

    return OperationsAssistant(
        name="operations_assistant", 
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class OperationsAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "operations", 
        name: str = "Operations Assistant", 
        description: str = "API endpoints to call the Operations assistant completion.", 
        description_stream: str = "API endpoints to call the Operations assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)