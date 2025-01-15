from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import PerplexityIntegration, NewsAPIIntegration, SerperIntegration
from src.integrations.SerperIntegration import SerperIntegrationConfiguration
from src.integrations.NewsAPIIntegration import NewsAPIIntegrationConfiguration
from src.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration

DESCRIPTION = "An Open Data Assistant that helps analyze external data sources and indicators."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/open_data_intelligence.png"
SYSTEM_PROMPT = f"""
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

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""

def create_open_data_assistant(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o", 
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    ) 

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
    
    # Add tools
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(PerplexityIntegrationConfiguration(api_key=perplexity_key))
    if news_api_key := secret.get('NEWS_API_KEY'):
        tools += NewsAPIIntegration.as_tools(NewsAPIIntegrationConfiguration(api_key=news_api_key))
    if serper_api_key := secret.get('SERPER_API_KEY'):
        tools += SerperIntegration.as_tools(SerperIntegrationConfiguration(api_key=serper_api_key))
    
    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=1), agent_configuration))
    
    return OpenDataAssistant(
        name="open_data_assistant", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
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