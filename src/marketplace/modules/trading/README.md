# Trading Module

## Overview

The Trading Module is a comprehensive solution for analyzing financial markets and managing trading strategies within the ABI platform. It provides tools for retrieving financial data, analyzing market trends, visualizing stock performance, and making informed trading decisions.

Key features include:

- **Financial Data Integration**: Connect to Yahoo Finance and other financial data providers to access real-time and historical market data
- **Stock Analysis**: Analyze stock price movements, earnings reports, and price variations over different time periods
- **Technical Indicators**: Access to moving averages and other technical analysis tools for identifying trends and patterns
- **Corporate Events Tracking**: Monitor earnings calls and other significant corporate events that may impact stock prices
- **Visualization**: Generate interactive charts and visualizations of stock performance data using Plotly
- **Trading Agent**: AI-powered stock trading assistant that helps analyze market data and provides trading recommendations
- **Ontology Support**: Comprehensive stock trading ontology for semantic representation of financial instruments and trading activities

## Getting Started

### Requirements

- Python 3.8 or higher
- pip package manager
- ABI Platform core installation
- The following Python packages:
  - pandas
  - plotly
  - langchain
  - rdflib
  - fastapi
  - requests

### Installation

1. **Install the module**:

```bash
pip install abi-trading-module
```

2. **Configure your environment**:

Create a `.env` file in your project root with the necessary credentials:

```
NAAS_API_KEY=your_naas_api_key
OPENAI_API_KEY=your_openai_api_key
```

3. **Basic setup for stock price analysis**:

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

4. **Working with the trading agent**:

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

The Trading Module is available in several tiers to meet the needs of different users:

### Free Tier
- Basic stock price data access
- Access to Yahoo Finance integration
- Standard price charts and analysis
- Limited to 100 requests per day
- Community support

### Professional Tier - $99/month
- Full stock analysis capabilities
- Technical indicator calculations
- Company earnings data
- AI-powered trading recommendations
- Interactive visualization capabilities
- Up to 1,000 requests per day
- Email support with 24-hour response time

### Enterprise Tier - Custom Pricing
- Everything in Professional tier
- Custom data provider integrations
- Advanced trading strategy development
- Backtesting capabilities
- Portfolio optimization tools
- Unlimited API requests
- Priority support with dedicated account manager
- SLA guarantees

Contact our sales team at sales@abiplatform.com for Enterprise pricing and customization options.

## Support

We're here to help you get the most out of the Trading Module:

### Documentation
Comprehensive documentation is available at [docs.abiplatform.com/trading](https://docs.abiplatform.com/trading)

### Community Support
- Join our [Discord community](https://discord.gg/abitrading)
- Post questions on our [Forum](https://forum.abiplatform.com)
- Check out the [FAQ](https://docs.abiplatform.com/trading/faq)

### Professional Support
- Professional and Enterprise customers can open support tickets through the [Customer Portal](https://support.abiplatform.com)
- Email: support@abiplatform.com
- Phone support available for Enterprise customers

### Contributing
We welcome community contributions to improve the Trading Module. Please see our [Contributing Guidelines](https://github.com/abiplatform/trading-module/CONTRIBUTING.md) for more information.
