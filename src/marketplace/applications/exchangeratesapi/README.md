# Exchange Rates API Module

## Overview

### Description

The Exchange Rates API Module provides comprehensive integration with Exchangeratesapi.io service for currency exchange rate data.

This module enables:
- Retrieving current exchange rates for any supported currency
- Accessing historical exchange rates for specific dates  
- Listing all available currency symbols and their names
- Automatic caching of responses to improve performance and reduce API calls
- LangChain tool integration for AI agent usage

### Requirements

API Key Setup:
1. Obtain an API key from [Exchangeratesapi.io](https://exchangeratesapi.io/)
2. Configure your `EXCHANGERATESAPI_API_KEY` in your environment

### TL;DR

To get started with the Exchange Rates API module:

1. Obtain an API key from [Exchangeratesapi.io](https://exchangeratesapi.io/)
2. Configure your `EXCHANGERATESAPI_API_KEY` in your environment

Test the integration using:
```bash
uv run python -m pytest src/marketplace/applications/exchangeratesapi/integrations/ExchangeratesapiIntegration_test.py
```

### Structure

```
src/marketplace/applications/exchangeratesapi/
├── integrations/
│   ├── ExchangeratesapiIntegration.py      # Main integration class
│   └── ExchangeratesapiIntegration_test.py # Integration tests
├── __init__.py                             # Module requirements check
└── README.md                               # This documentation
```

## Core Components

The module provides a single, focused integration for accessing exchange rate data from Exchangeratesapi.io.

### Integrations

#### Exchange Rates API Integration

The `ExchangeratesapiIntegration` class provides methods to interact with the Exchangeratesapi.io API endpoints, handling authentication and request management.

**Core Functions:**
- `list_symbols()`: Get all available currency symbols and names
- `get_exchange_rates()`: Get exchange rates for a specific date and base currency

##### Configuration

```python
from src.marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    ExchangeratesapiIntegration,
    ExchangeratesapiIntegrationConfiguration
)

# Create configuration
config = ExchangeratesapiIntegrationConfiguration(
    api_key="your_api_key_here"
)

# Initialize integration
integration = ExchangeratesapiIntegration(config)
```

##### Usage Examples

**Get Current Exchange Rates:**
```python
# Get latest rates with EUR as base currency
rates = integration.get_exchange_rates(date="latest", base="EUR")

# Get rates for specific currencies
rates = integration.get_exchange_rates(
    date="latest", 
    base="USD", 
    symbols=["EUR", "GBP", "JPY"]
)

# Get historical rates
rates = integration.get_exchange_rates(
    date="2024-01-15", 
    base="EUR"
)
```

**List Available Currencies:**
```python
# Get all available currency symbols
symbols = integration.list_symbols()
print(symbols["symbols"])  # Dictionary of currency codes and names
```

**Using with LangChain Tools:**
```python
from src.marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import as_tools

# Convert integration to LangChain tools
tools = as_tools(config)

# The tools will be available as:
# - exchangeratesapi_get_exchange_rates
# - exchangeratesapi_list_symbols
```

#### Testing

Run the integration tests to verify functionality:
```bash
uv run python -m pytest src/marketplace/applications/exchangeratesapi/integrations/ExchangeratesapiIntegration_test.py
```

**Test Coverage:**
- `test_list_symbols`: Verifies currency symbol retrieval
- `test_get_exchange_rates`: Tests exchange rate fetching with specific parameters

## API Endpoints

The module supports the following Exchangeratesapi.io endpoints:

- **GET /symbols**: List all available currencies
- **GET /{date}**: Get exchange rates for a specific date (use "latest" for current rates)

### Supported Parameters

**get_exchange_rates():**
- `date` (str): Date in YYYY-MM-DD format or "latest" for current rates
- `base` (str): Base currency code (default: "EUR")
- `symbols` (list[str]): List of target currency codes (default: all symbols)

**list_symbols():**
- No parameters required

## Caching

The module implements intelligent caching using the ABI cache framework to:
- Reduce API calls and improve performance
- Cache responses based on request parameters
- Store data in JSON format for easy access

**Cache Keys:**
- Exchange rates: `get_exchange_rates_{date}_{base}_{symbols}`
- Symbols: `list_symbols`

## Error Handling

The module includes comprehensive error handling:
- Network connection errors
- API authentication failures  
- Invalid request parameters
- Rate limiting responses

All errors are wrapped in `IntegrationConnectionError` for consistent error handling across the application.

## Rate Limits

Please refer to your Exchangeratesapi.io subscription plan for rate limits:
- **Free tier**: 100 requests per month
- **Paid plans**: Higher limits and additional features

The caching mechanism helps minimize API calls and stay within rate limits.

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework
- `abi.services.cache`: Caching functionality
- `langchain_core`: Tool integration for AI agents
- `pydantic`: Data validation and serialization
- `requests`: HTTP client for API calls

### External Services
- **Exchangeratesapi.io**: Currency exchange rate data provider

## Module Requirements

The module includes a requirements check in `__init__.py` that verifies the presence of `EXCHANGERATESAPI_API_KEY` in the environment. This ensures proper configuration before the module can be used.