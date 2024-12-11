from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.workflows.support_assistant import FeatureRequestWorkflow, ReportBugWorkflow, IssueListWorkflow

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
    model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = []

    # Add GetIssuesWorkflow tool
    tools.append(IssueListWorkflow.as_tool())

    # Add FeatureRequestWorkflow tool
    tools.append(FeatureRequestWorkflow.as_tool())
    
    # Add ReportBugWorkflow tool
    tools.append(ReportBugWorkflow.as_tool())
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SUPPORT_ASSISTANT_INSTRUCTIONS)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        model, 
        tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )