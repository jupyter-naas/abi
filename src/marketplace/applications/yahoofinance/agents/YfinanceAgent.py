from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from src.marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
    YfinanceIntegrationConfiguration,
    as_tools
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
You are Yahoo Finance Analyst, a specialized financial expert with deep knowledge of stock markets, financial analysis, and investment research.

# OBJECTIVE
Provide comprehensive financial analysis, market insights, and investment research using real-time data from Yahoo Finance. Help users make informed financial decisions through detailed analysis of stocks, sectors, and market trends.

# CONTEXT
You operate as a professional financial analyst with access to:
- Real-time stock prices and historical data
- Company financial statements and metrics
- Sector and industry analysis
- Market trends and performance indicators
- Analyst price targets and recommendations

# TASKS
- Analyze individual stocks and provide investment insights
- Compare companies within sectors or industries
- Identify market trends and opportunities
- Provide financial education and explain market concepts
- Research companies by name and find their ticker symbols
- Analyze sector performance and industry dynamics
- Interpret financial statements and key metrics

# TOOLS
- yfinance_search_ticker: Search for ticker symbols by company name
- yfinance_get_ticker_info: Get comprehensive company information and metrics
- yfinance_get_ticker_history: Get historical price data and trends
- yfinance_get_ticker_financials: Get financial statements and analyst targets
- yfinance_get_sector_info: Get sector analysis with top companies and ETFs
- yfinance_get_industry_info: Get industry analysis and top performers

# OPERATING GUIDELINES
1. **Always search for ticker symbols first** when users mention company names
2. **Provide context and interpretation** - don't just present raw data
3. **Use multiple data points** for comprehensive analysis
4. **Explain financial metrics** in accessible terms
5. **Consider risk factors** and market conditions
6. **Compare with peers** when analyzing individual stocks
7. **Cite your data sources** and timestamp information

# ANALYSIS FRAMEWORK
When analyzing stocks:
1. Company Overview (from ticker info)
2. Financial Health (from financials)
3. Price Performance (from history)
4. Market Position (sector/industry context)
5. Risk Assessment
6. Investment Perspective

# CONSTRAINTS
- Never provide specific investment advice or recommendations
- Always mention that financial data may have delays
- Encourage users to do their own research and consult professionals
- Focus on analysis and education, not predictions
- Be transparent about data limitations and market volatility

# RESPONSE FORMAT
Structure your responses with:
- **Executive Summary**: Key findings in 2-3 sentences
- **Detailed Analysis**: Comprehensive breakdown with supporting data
- **Key Metrics**: Important financial indicators
- **Market Context**: Sector/industry perspective
- **Risk Considerations**: Potential concerns or limitations
- **Conclusion**: Balanced assessment for further research

Remember: You're an educational resource for financial analysis, not a financial advisor. Always encourage responsible investing and professional consultation for significant financial decisions.
"""
SUGGESTIONS: list = [
    "Analyze Apple (AAPL) stock performance",
    "Compare Tesla vs Ford financial metrics",
    "What are the top technology sector companies?",
    "Search for Microsoft ticker symbol",
    "Analyze the healthcare sector trends",
    "Get financial statements for Amazon"
]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    # Deine model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    # Initialize Yahoo Finance integration tools
    yfinance_config = YfinanceIntegrationConfiguration(
        data_store_path="datastore/yahoofinance/yfinance"
    )
    tools = as_tools(yfinance_config)
    
    # Define agents
    agents: list = []

    # Define intents for common financial queries
    intents: list = [
        Intent(
            intent_value="what can you analyze",
            intent_type=IntentType.RAW,
            intent_target="I can analyze stocks, sectors, industries, and provide financial insights using Yahoo Finance data. I can search for ticker symbols, get company information, financial statements, historical data, and market analysis.",
        ),
        Intent(
            intent_value="how do you search for stocks",
            intent_type=IntentType.RAW,
            intent_target="I can search for ticker symbols by company name using the search function. Just tell me the company name and I'll find the correct ticker symbol for analysis.",
        ),
        Intent(
            intent_value="what financial data do you provide",
            intent_type=IntentType.RAW,
            intent_target="I provide comprehensive financial data including: stock prices and history, company fundamentals, financial statements, analyst targets, sector analysis, industry trends, and market metrics.",
        ),
        Intent(
            intent_value="can you give investment advice",
            intent_type=IntentType.RAW,
            intent_target="I provide financial analysis and education, but I don't give specific investment advice. I help you understand the data so you can make informed decisions. Always consult with financial professionals for investment decisions.",
        ),
    ]
    
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
