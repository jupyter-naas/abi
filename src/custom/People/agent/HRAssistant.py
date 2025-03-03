from typing import List
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from langgraph.checkpoint.memory import MemorySaver
from src import secret
from src.custom.People.workflows.HRTalentWorkflow import HRTalentWorkflow, HRTalentWorkflowConfiguration

# Constants
NAME = "HR Assistant"
DESCRIPTION = "An AI assistant specialized in human resources tasks, including recruitment, employee management, and HR policies."
MODEL = "gpt-4-turbo-preview"
TEMPERATURE = 0.7
SYSTEM_PROMPT = """You are an HR Assistant specialized in human resources tasks. Your responsibilities include:
1. Assisting with recruitment and hiring processes
2. Providing guidance on HR policies and procedures
3. Helping with employee onboarding and offboarding
4. Answering questions about benefits and compensation
5. Handling employee relations and workplace issues
6. Supporting performance management processes
7. Ensuring compliance with labor laws and regulations

You have access to tools for:
- Talent finding
- Schema retrieval
- Query execution

Before executing a query, you should make sure that you retrieve the schema of the ontology to make sure that the query is valid.

Always maintain professionalism and confidentiality in your responses."""

def create_hr_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
) -> Agent:
    """Creates an HR agent with the specified configuration.
    
    Args:
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
        
    Returns:
        Agent: The configured HR agent
    """
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get('OPENAI_API_KEY')
    )
    
    # Initialize tools list with HR talent workflow tools
    hr_talent_workflow = HRTalentWorkflow(HRTalentWorkflowConfiguration())
    tools: List[Tool] = hr_talent_workflow.as_tools()
    
    # Initialize agents list - will be expanded as needed
    agents: List[Agent] = []
    
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    )
