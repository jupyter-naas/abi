from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src.workflows import tools as workflow_tools
from src import secret

def create_custom_workflow_agent(agent_shared_state: AgentSharedState, agent_configuration: AgentConfiguration):
    """Creates a custom workflow agent with workflow-specific tools.
    
    Args:
        agent_shared_state (AgentSharedState): Shared state for the agent
        agent_configuration (AgentConfiguration): Configuration for the agent
        
    Returns:
        Agent: Configured workflow agent
    """
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    # You can customize which workflow tools to include here
    tools = workflow_tools
    
    return Agent(
        model, 
        tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 