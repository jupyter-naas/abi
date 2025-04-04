from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import YahooFinanceIntegration
from src.core.modules.common.integrations.YahooFinanceIntegration import YahooFinanceIntegrationConfiguration
from src.core.modules.support.agents.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Yahoo Finance Assistant for financial data retrieval and analysis."
AVATAR_URL = "https://logo.clearbit.com/finance.yahoo.com"
SYSTEM_PROMPT = f"""
You are a Yahoo Finance Assistant with access to YahooFinanceIntegration tools.
If you don't have access to any tool, ask the user to set their YAHOO_FINANCE_API_KEY in .env file for premium features.
Always be clear and professional in your communication while helping users retrieve and analyze financial data.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_yahoo_finance_agent():
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
    
    # Initialize integration (API key optional for basic features)
    integration_config = YahooFinanceIntegrationConfiguration(
        api_key=secret.get('YAHOO_FINANCE_API_KEY', None)  # Optional for basic features
    )
    tools += YahooFinanceIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="yahoo_finance_agent",
        description="Use to retrieve and analyze financial market data",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 