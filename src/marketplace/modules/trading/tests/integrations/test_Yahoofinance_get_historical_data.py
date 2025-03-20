from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration

# Create a configuration with default or custom settings
config = YahooFinanceIntegrationConfiguration(
    max_retries=5,  # Optional: override defaults
    retry_delay=2   # Optional: override defaults
)

# Initialize the integration
yahoo_finance = YahooFinanceIntegration(config)

# Get historical data (timestamp periods in Unix time)
symbol = "AVGO"
period1 = 1709683200
period2 = 1742374163
frequency = "1d"

historical_data = yahoo_finance.get_historical_data(
    symbol=symbol, 
    period1=period1,  # Start date
    period2=period2,  # End date
    frequency=frequency       # Daily data
)