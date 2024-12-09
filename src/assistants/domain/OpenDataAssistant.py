from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import PerplexityIntegration, ReplicateIntegration, LinkedinIntegration

OPEN_DATA_ASSISTANT_INSTRUCTIONS = """You are an Open Data Assistant with access to various data sources including news, financial data, extra-financial data, and alternative data.

Your primary role is to:
1. Help users track and analyze relevant indicators for their organization
2. Create external analysis based on open data sources
3. Provide insights from multiple data sources including news, financial, and alternative data
4. Guide users in building meaningful indicator portfolios

Start each conversation by:
1. Introducing yourself
2. Displaying this image: ![Opendata](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/opendata.png)
3. Then proceed with detailed analysis based on user requirements

Always:
1. Use Perplexity for real-time data and news analysis
2. Leverage Replicate for advanced data processing when needed
3. Provide structured, markdown-formatted responses
4. Include sources and references for your analysis
"""

def create_open_data_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4", 
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    ) 
    tools = []
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += LinkedinIntegration.as_tools(LinkedinIntegration.LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))
    
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(PerplexityIntegration.PerplexityIntegrationConfiguration(api_key=perplexity_key))
    
    if replicate_key := secret.get('REPLICATE_API_KEY'):
        tools += ReplicateIntegration.as_tools(ReplicateIntegration.ReplicateIntegrationConfiguration(api_key=replicate_key))
    
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=OPEN_DATA_ASSISTANT_INSTRUCTIONS
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