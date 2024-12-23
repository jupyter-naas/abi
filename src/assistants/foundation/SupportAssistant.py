from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.workflows.support_assistant import FeatureRequestWorkflow, ReportBugWorkflow, IssueListWorkflow

DESCRIPTION = "A Support Assistant that helps to get any feedbacks/bugs or needs from user."
SUPPORT_ASSISTANT_INSTRUCTIONS = """
You are a support assistant focusing creating GitHub Issues to request new features or report bugs.
1. Identify if the user intent is a "feature_request" or "bug_report".
A feature request can be a new integration with an external API not existing in our project yet, a new ontology pipeline (Mapping integration function to Ontology) or a new workflow using integration and/or pipeline to resolve specific needs.
A bug report is a problem with an existing integration, pipeline or workflow.
2. Get all issues from the GitHub repository using the `list_github_issues` tool and check if a corresponding issue already exists.
3. Perform actions: 
- If the user intent does not match any existing issue, create issue.
- If the user intent match with an existing issue, ask the user if they want to create a new one, update the existing one or do nothing.
"""

def create_support_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    if github_access_token := secret.get('GITHUB_ACCESS_TOKEN'):
        github_integration_config = GithubIntegrationConfiguration(access_token=github_access_token)
        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=github_access_token)

        # Add GetIssuesWorkflow tool
        get_issues_workflow = IssueListWorkflow.IssueListWorkflow(IssueListWorkflow.IssueListWorkflowConfiguration(
            github_integration_config=github_integration_config
        ))
        tools += get_issues_workflow.as_tools()

        # Add FeatureRequestWorkflow tool
        feature_request_workflow = FeatureRequestWorkflow.FeatureRequestWorkflow(FeatureRequestWorkflow.FeatureRequestWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        ))
        tools += feature_request_workflow.as_tools()
        
        # Add ReportBugWorkflow tool
        report_bug_workflow = ReportBugWorkflow.ReportBugWorkflow(ReportBugWorkflow.ReportBugWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        ))
        tools += report_bug_workflow.as_tools()
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SUPPORT_ASSISTANT_INSTRUCTIONS)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="support_assistant", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )