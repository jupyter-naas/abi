from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import NewsAPIIntegration
from src.core.integrations.NewsAPIIntegration import NewsAPIIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A NewsAPI Assistant for retrieving news articles and headlines."
AVATAR_URL = "https://newsapi.org/images/n-logo-border.png"
SYSTEM_PROMPT = f"""
You are a NewsAPI Assistant with access to NewsAPIIntegration tools.
If you don't have access to any tool, ask the user to set their NEWSAPI_API_KEY in .env file.
Always be clear and professional in your communication while helping users retrieve news content.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

When searching for news:
- Help users formulate specific queries
- Suggest relevant categories or sources when applicable
- Explain how to filter results by date, language, or source
- Provide context about the news results returned

{RESPONSIBILITIES_PROMPT}
"""

def create_news_api_agent():
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
    if secret.get('NEWSAPI_API_KEY'):    
        integration_config = NewsAPIIntegrationConfiguration(
            api_key=secret.get('NEWSAPI_API_KEY')
        )
        tools += NewsAPIIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="news_api_agent",
        description="Use to search and retrieve news articles and headlines",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 