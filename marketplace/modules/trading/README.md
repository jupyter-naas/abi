# Trading Module

## Overview

The Trading Module is a comprehensive solution for analyzing financial markets and managing trading strategies within the ABI platform. It provides tools for retrieving financial data, analyzing market trends, visualizing stock performance, and making informed trading decisions.

Key features include:

- **Earnings Call Calendar**: Connect to Yahoo Finance to access the earnings call calendar.
- **Stock Analysis**: Analyze stock price movements with moving averages 20 and 50, and price variations over different time periods
- **Visualization**: Generate charts with stock performance, moving averages and earning calls dates.
- **Trading Agent**: Trading assistant that helps analyze market data and provides trading recommendations BUY, HOLD, SELL.

## Getting Started

### Requirements

- Create your account on OpenAI and get your API key.
- Create your account on Naas.ai and get your API key.
- Setup project with Naas API key, workspace ID and OpenAI API key.

### Installation

Setup your environment with the following variables:

```
NAAS_API_KEY=your_naas_api_key
OPENAI_API_KEY=your_openai_api_key
```

### Usage

1. **Basic setup for stock price analysis**:

```python
from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration
from src.core.modules.common.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.marketplace.modules.trading.workflows.StockPriceAnalysisWorkflow import StockPriceAnalysisWorkflow, StockPriceAnalysisWorkflowConfiguration, StockPriceAnalysisWorkflowParameters

# Setup integrations
yahoo_finance_config = YahooFinanceIntegrationConfiguration()
naas_config = NaasIntegrationConfiguration(api_key="your_naas_api_key")

# Configure workflow
workflow_config = StockPriceAnalysisWorkflowConfiguration(
    yahoo_finance_integration_config=yahoo_finance_config,
    naas_integration_config=naas_config
)

# Initialize workflow
stock_analysis = StockPriceAnalysisWorkflow(workflow_config)

# Analyze a stock
result = stock_analysis.get_stock_price_analysis(
    StockPriceAnalysisWorkflowParameters(
        symbol="AAPL",
        currency="USD"
    )
)

print(f"Analysis chart URL: {result}")
```

2. **Working with the trading agent**:

```python
from src.marketplace.modules.trading.agents.StockTradingAgent import create_agent
from abi.services.agent.Agent import AgentConfiguration

# Create trading agent
agent = create_agent()

# Ask the agent for analysis
response = agent.completion("Can you analyze the current market conditions for Apple?")
print(response)
```

## Pricing

The Trading Module is free while using your own API keys.

## Support

Contact us at florent@naas.ai for any questions or support requests.