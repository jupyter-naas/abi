"""Yahoo Finance agent: an SDK IntentAgent hosted by the remote ``yahoofinance`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.yahoofinance.integrations.YfinanceIntegration import (
    YfinanceIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent, Intent, IntentType

NAME = "YahooFinance"
DESCRIPTION = "Expert financial analyst agent specialized in stock market research, sector analysis, and financial data interpretation using Yahoo Finance."
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

INTENTS: list[Intent] = [
    Intent(
        intent_value="search for company ticker",
        intent_type=IntentType.TOOL,
        intent_target="yfinance_search_ticker",
    ),
    Intent(
        intent_value="get company information",
        intent_type=IntentType.TOOL,
        intent_target="yfinance_get_ticker_info",
    ),
    Intent(
        intent_value="get stock price history",
        intent_type=IntentType.TOOL,
        intent_target="yfinance_get_ticker_history",
    ),
    Intent(
        intent_value="get financial statements",
        intent_type=IntentType.TOOL,
        intent_target="yfinance_get_ticker_financials",
    ),
    Intent(
        intent_value="get sector analysis",
        intent_type=IntentType.TOOL,
        intent_target="yfinance_get_sector_info",
    ),
    Intent(
        intent_value="get industry analysis",
        intent_type=IntentType.TOOL,
        intent_target="yfinance_get_industry_info",
    ),
]


async def create_agent(
    engine: Any,
    module_id: str,
    *,
    datastore_path: str = "yahoofinance",
    chat_model: str = "",
) -> Agent:
    """``engine`` declares ``model_registry``, ``document`` and ``object_storage``."""
    tools = as_tools(
        YfinanceIntegrationConfiguration(
            datastore_path=datastore_path, storage=engine.services.object_storage
        )
    )
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        intents=INTENTS,
        chat_model=chat_model,
    )
