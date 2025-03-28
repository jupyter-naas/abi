from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import GoogleAnalyticsIntegration
from src.core.modules.common.integrations.GoogleAnalyticsIntegration import GoogleAnalyticsIntegrationConfiguration
from src.core.modules.support.assistants.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Google Analytics Assistant for accessing and analyzing website analytics data."
AVATAR_URL = "https://logos-world.net/wp-content/uploads/2021/02/Google-Analytics-Logo.png"
SYSTEM_PROMPT = f"""
You are a Google Analytics Assistant with access to GoogleAnalyticsIntegration tools.
If you don't have access to any tool, ask the user to set up their Google Analytics credentials in .env file.
Always be clear and professional in your communication while helping users analyze their website data.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_google_analytics_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    if secret.get('GOOGLE_ANALYTICS_CREDENTIALS'):    
        integration_config = GoogleAnalyticsIntegrationConfiguration(
            credentials=secret.get('GOOGLE_ANALYTICS_CREDENTIALS')
        )
        tools += GoogleAnalyticsIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="google_analytics_agent",
        description="Use to analyze website traffic and user behavior data",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 