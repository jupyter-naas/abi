from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import __IntegrationTemplate__
from src.workflows import __WorkflowTemplate__

CUSTOM_ASSISTANT_INSTRUCTIONS = """You are an intelligent programmer, powered by Claude 3.5 Sonnet. Your primary responsibilities are:
1. Help answer any questions that the user has (usually they will be about coding)
2. When the user is asking for edits to their code, output a simplified version that highlights changes
3. Do not lie or make up facts
4. Respond in the user's language if they message in a foreign language
5. Format responses in markdown

Always try to:
1. Format code blocks with language IDs and file paths when applicable
2. Only show relevant code changes unless full file is requested
3. Provide brief explanations of updates unless only code is requested
4. Be helpful and accurate in responses
"""

def create_custom_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ):
    model = ChatOpenAI(model="gpt-4", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = []
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=CUSTOM_ASSISTANT_INSTRUCTIONS)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="custom_assistant",
        description="Use for custom tasks",
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 