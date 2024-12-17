from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config
from src.integrations import AiaIntegration, NaasIntegration
from src.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.workflows.operations_assistant.CreateIssueAndAddToProjectWorkflow import CreateIssueAndAddToProjectWorkflow, CreateIssueAndAddToProjectWorkflowConfiguration
from src.workflows.operations_assistant.GetTopPrioritiesWorkflow import GetTopPrioritiesWorkflow, GetTopPrioritiesConfiguration
from src.workflows.operations_assistant.AssignIssuesToProjectWorkflow import AssignIssuesToProjectWorkflow, AssignIssuesToProjectWorkflowConfiguration
from src.workflows.operations_assistant.AddAssistantsToNaasWorkspaceWorkflow import AddAssistantsToNaasWorkspace, AddAssistantsToNaasWorkspaceConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.data.pipelines.github.GithubIssuesPipeline import GithubIssuesPipeline, GithubIssuesPipelineConfiguration
from src.data.pipelines.github.GithubUserDetailsPipeline import GithubUserDetailsPipeline, GithubUserDetailsPipelineConfiguration
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An Operations Assistant that manages tasks and projects to improve operational efficiency."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/operations_efficiency.png"
SYSTEM_PROMPT = f'''
You are an Operations Assistant.
Your primary role is to enhance operational efficiency by accessing Task and Project management tools.

{RESPONSIBILITIES_PROMPT}
'''

def create_operations_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    tools = []
    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))

    # Add integrations & workflbased on available credentials
    if naas_key := secret.get('NAAS_API_KEY'):
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_key)

        # Add AddAssistantsToNaasWorkspace tool
        add_assistants_to_naas_workspace = AddAssistantsToNaasWorkspace(AddAssistantsToNaasWorkspaceConfiguration(
            naas_integration_config=naas_integration_config
        ))
        tools += add_assistants_to_naas_workspace.as_tools()

    if (naas_key := secret.get('NAAS_API_KEY')) and (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        aia_integration_config = AiaIntegration.AiaIntegrationConfiguration(api_key=naas_key)
        tools += AiaIntegration.as_tools(aia_integration_config)

    if github_access_token := secret.get('GITHUB_ACCESS_TOKEN'):
        github_integration_config = GithubIntegrationConfiguration(access_token=github_access_token)
        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=github_access_token)

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
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="operations_assistant", 
        description="Use for operations and marketing analysis",
        chat_model=model,
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 