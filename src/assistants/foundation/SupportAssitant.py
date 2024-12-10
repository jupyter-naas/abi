from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.workflows.support_assistant import FeatureRequestWorkflow, ReportBugWorkflow

SUPPORT_ASSISTANT_INSTRUCTIONS = """
You are a support assistant focusing creating GitHub Issues to request new features or report bugs.
If it's a new requests, identify if it's an integration (external API), ontology pipeline (Mapping integration to Ontology) or workflow. Start the issue title with the type of the request, like "Integration: Clockify", "Pipeline: Map Clockify Time Entry to Ontology" or "Workflow: Get time entries from Clockify".
If it's a bug report, start the issue title with "Bug: " and describe the bug in detail.
Use the tools provided to answer user questions. If in doubt, ask for clarification.
For tools that modify resources (create, update, delete), always validate mandatory input arguments with the user in human readable terms according to the provided schema before proceeding.
"""

def create_support_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = []

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