from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class YfinanceAgent(IntentAgent):
    name: str = "YahooFinance"
    description: str = "Expert financial analyst agent specialized in stock market research, sector analysis, and financial data interpretation using Yahoo Finance."
    avatar_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/yahoo_finance_logo.png"
    )
    system_prompt: str = """# ROLE
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

    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "YfinanceAgent":
        from naas_abi_core.engine.context import get_default_model_registry
        from naas_abi_marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
            YfinanceIntegrationConfiguration,
            as_tools,
        )

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        yfinance_config = YfinanceIntegrationConfiguration()
        tools = as_tools(yfinance_config)

        intents: list = [
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

        system_prompt = cls.system_prompt.replace(
            "[TOOLS]",
            "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]),
        )
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
