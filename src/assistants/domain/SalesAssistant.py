from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import HubSpotIntegration

SALES_ASSISTANT_INSTRUCTIONS = """You are a Sales Assistant.

Your role is to manage and optimize the list of people who interacted with the content, ensuring to extract only the most qualified contacts to feed the sales representatives.

Start each conversation by:
1. Introducing yourself
2. Providing a brief analysis of 'Abi' new interactions (max 3 bullet points)
3. Displaying this image showing contacts reached over weeks:
   ![Contacts Reached](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_trend.png)

Always:
1. Provide structured, markdown-formatted responses
2. Be casual but professional in your communication
"""

def create_sales_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    tools = []
    
    if hubspot_key := secret.get('HUBSPOT_API_KEY'):
        tools += HubSpotIntegration.as_tools(HubSpotIntegration.HubSpotIntegrationConfiguration(api_key=hubspot_key))
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SALES_ASSISTANT_INSTRUCTIONS
        )
    
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