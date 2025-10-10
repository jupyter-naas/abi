# Agicap Module

## Overview

### Description

The Agicap Module provides comprehensive integration with Agicap's cash flow management platform, enabling intelligent financial analysis, real-time cash flow monitoring, and strategic financial decision-making through AI-powered insights.

This module enables:
- **Cash Flow Analytics**: Real-time analysis, forecasting, and scenario modeling
- **Financial Intelligence**: Pattern recognition, trend analysis, and predictive insights  
- **Risk Management**: Liquidity monitoring, credit assessment, and early warning systems
- **Operational Excellence**: Automated reconciliation, payment optimization, and workflow efficiency
- **Multi-language Support**: Native French and English communication capabilities

### Requirements

#### API Keys Setup

To use the Agicap module, you need to configure the following environment variables in your `.env` file:

**Required Environment Variables:**
- `AGICAP_USERNAME`: Username of your Agicap account
- `AGICAP_PASSWORD`: Password of your Agicap account  
- `AGICAP_CLIENT_ID`: Client ID from your Agicap organization settings
- `AGICAP_CLIENT_SECRET`: Client Secret from your Agicap organization settings
- `AGICAP_BEARER_TOKEN`: Bearer Token for private API access (auto-generated if not provided)
- `AGICAP_API_TOKEN`: API token for public API access
- `OPENAI_API_KEY`: OpenAI API key for the AI agent functionality

#### How to Obtain Agicap API Credentials

1. **Login to Agicap**: Access your Agicap account at [app.agicap.com](https://app.agicap.com)

2. **Get Client ID & Client Secret**:
   - Navigate to: Organization Settings → Advanced Settings → Public API
   - Or directly access: [Public API Settings](https://app.agicap.com/fr/app/organization-advanced-settings/public-api)
   - Generate or copy your `Client ID` and `Client Secret`

3. **Get API Token**:
   - Navigate to: Settings → OpenAPI
   - Or directly access: [OpenAPI Settings](https://app.agicap.com/fr/app/parametres/openapi)
   - Generate or copy your `API Token`

4. **Bearer Token**: This will be automatically generated during authentication if not provided

### TL;DR

To get started with the Agicap module:

1. Configure your Agicap credentials in `.env`:
   ```bash
   AGICAP_USERNAME=your_username
   AGICAP_PASSWORD=your_password
   AGICAP_CLIENT_ID=your_client_id
   AGICAP_CLIENT_SECRET=your_client_secret
   AGICAP_API_TOKEN=your_api_token
   OPENAI_API_KEY=your_openai_key
   ```

2. Start chatting with the Agicap agent:
   ```bash
   make chat agent=agicap
   ```

### Structure

```
src/marketplace/applications/agicap/
├── agents/                         
│   └── AgicapAgent.py              # Financial analysis AI agent
├── integrations/                    
│   └── AgicapIntegration.py        # Agicap API integration
├── sandbox/                        # Development and testing area
├── __init__.py                     # Module initialization
└── README.md                       # This documentation
```

## Core Components

### Agents

#### Agicap Agent

Expert financial analyst and cash flow management specialist powered by advanced AI capabilities.

**Capabilities:**
- **Intelligent Financial Analysis**: Advanced cash flow analytics with predictive insights
- **Multi-tool Orchestration**: Seamlessly combines multiple Agicap API endpoints
- **Bilingual Communication**: Natural conversation in French and English
- **Intent-driven Interactions**: Smart routing to appropriate financial tools
- **Strategic Advisory**: Executive-level insights with actionable recommendations

**Key Intents:**
- Company and account discovery
- Transaction analysis and monitoring
- Cash flow forecasting and analysis
- Debt management and risk assessment
- Financial reporting and dashboards

**Usage Examples:**
```bash
# Start agent
make chat agent=AgicapAgent

# Example queries (French)
"Analyse ma trésorerie"
"Quelles sont mes compagnies disponibles?"
"Crée un tableau de bord financier"

# Example queries (English)
"Analyze my cash flow"
"Show me my company accounts"
"Generate a financial report"
```

#### Testing
```bash
# Run agent tests
uv run python -m pytest src/marketplace/applications/agicap/agents/AgicapAgent_test.py -v
```

### Integrations

#### Agicap Integration

Enhanced integration with Agicap's API featuring robust error handling, automatic token management, and comprehensive financial data access.

**Core Methods:**
- `list_companies()`: Retrieve accessible companies
- `get_company_accounts(company_id)`: Get accounts for a company
- `get_transactions(company_id, account_id, **filters)`: Fetch transaction data with filtering
- `get_balance(company_id, account_id, **options)`: Retrieve balance information with forecasts
- `get_debts(company_id, **options)`: Access debt information with analytics

**Enhanced Features:**
- **Automatic Token Refresh**: Handles authentication seamlessly
- **Rate Limiting**: Respects API limits with intelligent retry logic
- **Enhanced Error Handling**: Comprehensive error reporting and recovery
- **Data Enrichment**: Adds metadata and analytics to raw API responses
- **Flexible Filtering**: Advanced date ranges and transaction type filtering

##### Configuration

```python
from src.marketplace.applications.agicap.integrations.AgicapIntegration import (
    AgicapIntegration,
    AgicapIntegrationConfiguration
)

# Create configuration
config = AgicapIntegrationConfiguration(
    username="your_username",
    password="your_password",
    client_id="your_client_id",
    client_secret="your_client_secret",
    api_token="your_api_token",
)

# Initialize integration
integration = AgicapIntegration(config)

# Example usage
companies = integration.list_companies()
accounts = integration.get_company_accounts("company_id")
transactions = integration.get_transactions(
    "company_id", 
    "account_id", 
    limit=100,
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

#### Available Tools

The integration exposes the following LangChain tools for the AI agent:

1. **`agicap_list_companies`**: Discover available companies
2. **`agicap_get_company_accounts`**: Retrieve company bank accounts
3. **`agicap_get_transactions`**: Fetch and analyze transactions
4. **`agicap_get_balance`**: Monitor cash positions and forecasts
5. **`agicap_get_debts`**: Analyze debt portfolio and risks

#### Testing
```bash
# Run integration tests
uv run python -m pytest src/marketplace/applications/agicap/integrations/AgicapIntegration_test.py -v
```

## Key Features

### 🔄 **Intelligent Financial Orchestration**
Seamlessly combines multiple financial data sources for comprehensive analysis

### 🌍 **Bilingual Financial Communication**
Native French/English support with financial terminology expertise

### 🎯 **Intent-Driven Interactions**
Smart routing from natural language to specific financial operations

### 📊 **Advanced Analytics**
Transforms raw financial data into strategic business intelligence

### 🔒 **Secure & Robust**
Enterprise-grade security with automatic token management and error recovery

### ⚡ **Real-time Insights**
Live financial data with predictive analytics and risk monitoring

## Use Cases

### Cash Flow Management
- Monitor real-time cash positions across multiple accounts
- Generate cash flow forecasts with scenario analysis
- Identify liquidity risks and optimization opportunities

### Financial Reporting
- Create comprehensive financial dashboards
- Generate executive-level financial reports
- Perform variance analysis against budgets

### Risk Assessment
- Monitor debt portfolio and payment obligations
- Identify overdue accounts and credit risks
- Set up automated financial alerts

### Transaction Analysis
- Analyze spending patterns and trends
- Track payment flows and reconciliation
- Identify anomalies and potential fraud

## Dependencies

### Python Libraries
- `lib.abi.integration`: Base integration framework
- `abi.services.agent`: Intent-based agent framework
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: OpenAI language model integration
- `fastapi`: API router for agent endpoints
- `pydantic`: Data validation and serialization
- `requests`: HTTP client for Agicap API calls
- `datetime`: Date and time handling utilities

### External Services
- **Agicap API**: Cash flow management platform
- **OpenAI API**: GPT models for natural language processing

## Security & Best Practices

### Credential Management
- Store all sensitive credentials in environment variables
- Never commit API keys to version control
- Use the provided configuration classes for secure credential handling

### Rate Limiting
- Built-in rate limiting respects Agicap API constraints
- Automatic retry logic with exponential backoff
- Configurable timeout and retry settings

### Error Handling
- Comprehensive error reporting with detailed logging
- Graceful fallback for network issues
- Automatic token refresh for expired credentials

### Data Privacy
- All financial data handling follows enterprise security standards
- No persistent storage of sensitive financial information
- Secure transmission with HTTPS encryption

## Troubleshooting

### Common Issues

**Authentication Errors:**
- Verify all API credentials are correctly configured
- Check that your Agicap account has API access enabled
- Ensure Bearer Token is valid or let the system auto-generate it

**Connection Issues:**
- Verify network connectivity to Agicap services
- Check if you're behind a corporate firewall
- Review timeout settings in configuration

**Data Issues:**
- Ensure you have access to the requested company data
- Verify company and account IDs are correct
- Check date ranges for transaction queries

### Getting Help

1. Check the error logs for detailed error messages
2. Verify your API credentials and permissions
3. Test individual integration methods
4. Contact Agicap support for API-specific issues

## Contributing

When contributing to the Agicap module:

1. Follow the existing code patterns and documentation style
2. Add comprehensive tests for new features
3. Update this README for any new capabilities
4. Ensure all API interactions follow rate limiting guidelines
5. Test with real Agicap data when possible (with appropriate permissions)
