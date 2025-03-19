from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration

# Create a configuration with default or custom settings
config = YahooFinanceIntegrationConfiguration(
    max_retries=5,  # Optional: override defaults
    retry_delay=2   # Optional: override defaults
)

# Initialize the integration
yahoo_finance = YahooFinanceIntegration(config)

# Symbol
symbol = "AVGO"

# Get earnings calls
earnings_calls = yahoo_finance.get_earnings_calls(
    symbol=symbol
)