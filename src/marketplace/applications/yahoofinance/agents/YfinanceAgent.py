from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)

from typing import Optional
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret

NAME = "YahooFinance"
DESCRIPTION = "Expert financial analyst agent specialized in stock market research, sector analysis, and financial data interpretation using Yahoo Finance."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/yahoo_finance_logo.png"
MODEL = "gpt-4.1-mini"
TEMPERATURE = 0
SYSTEM_PROMPT = """# ROLE
You are a Yahoo Finance data specialist focused on retrieving and analyzing financial data through the yfinance API tools.

# OBJECTIVE
Provide accurate financial data and analysis by effectively utilizing the yfinance tools to search, retrieve and interpret stock market information.

# CONTEXT
You have access to Yahoo Finance data through specialized tools:
- Company search and ticker symbol lookup
- Real-time and historical price data
- Financial statements and metrics
- Sector and industry analysis
- Market performance indicators

# TASKS
• Search and validate company information and symbols
• Gather comprehensive financial and market data
• Present clear analysis and insights from the data

# TOOLS
[TOOLS]

# OPERATING GUIDELINES
1. Start with ticker search for any company analysis
2. Validate data before presenting results
3. Use appropriate tools for specific information needs
4. Present data clearly with proper context
5. Acknowledge limitations of available data
6. Combine tools for comprehensive analysis
7. Cite data sources and timestamps

# CONSTRAINTS
- Only use provided yfinance tools for data retrieval
- Never provide specific investment advice
- Always mention potential data delays
- Focus on data presentation and analysis
- Be transparent about tool limitations
"""

SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> IntentAgent:
    # Deine model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    # Initialize Yahoo Finance integration tools
    from src.marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
        YfinanceIntegrationConfiguration,
        as_tools
    )
    yfinance_config = YfinanceIntegrationConfiguration()
    tools = as_tools(yfinance_config)
    
    # Define agents
    agents: list = []

    # Define intents for each yfinance tool
    intents: list = [
        Intent(intent_value="search for company ticker", intent_type=IntentType.TOOL, intent_target="yfinance_search_ticker"),
        Intent(intent_value="get company information", intent_type=IntentType.TOOL, intent_target="yfinance_get_ticker_info"),
        Intent(intent_value="get stock price history", intent_type=IntentType.TOOL, intent_target="yfinance_get_ticker_history"),
        Intent(intent_value="get financial statements", intent_type=IntentType.TOOL, intent_target="yfinance_get_ticker_financials"),
        Intent(intent_value="get sector analysis", intent_type=IntentType.TOOL, intent_target="yfinance_get_sector_info"),
        Intent(intent_value="get industry analysis", intent_type=IntentType.TOOL, intent_target="yfinance_get_industry_info"),
    ]

    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace("[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]))
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return YfinanceAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class YfinanceAgent(IntentAgent):
    pass
