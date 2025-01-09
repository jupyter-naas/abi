from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import PerplexityIntegration
from fastapi import APIRouter

DESCRIPTION = "An Open Data Assistant that helps analyze external data sources and indicators."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/open_data_intelligence.png"
SYSTEM_PROMPT = """
You are an Open Data Assistant with access to various data sources including news, financial data, extra-financial data, and alternative data.

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
        model="gpt-4o", 
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    ) 
    tools = []
    
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(PerplexityIntegration.PerplexityIntegrationConfiguration(api_key=perplexity_key))
    
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return OpenDataAssistant(
        name="open_data_assistant", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class OpenDataAssistant(Agent):
    def as_api(
            self, 
            router: APIRouter, 
            route_name: str = "open_data", 
            name: str = "Open Data Assistant", 
            description: str = "API endpoints to call the Open Data assistant completion.", 
            description_stream: str = "API endpoints to call the Open Data assistant stream completion.",
            tags: list[str] = []
        ):
        return super().as_api(router, route_name, name, description, description_stream, tags)