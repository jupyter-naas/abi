"""
Bitcoin Price Integration

Provides integration with Bitcoin price data sources like Yahoo Finance and CoinGecko.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
import yfinance as yf
import requests

# Import order matters - we need to import our tools framework first
from langchain_core.tools import Tool

# Try the direct approach - create our own base classes
class IntegrationConfiguration:
    """Base configuration class for integrations."""
    pass

class Integration:
    """Base class for integrations."""
    def __init__(self, configuration):
        self.configuration = configuration
    
    def as_tools(self):
        """Return the integration's tools."""
        return []

@dataclass
class BitcoinPriceIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for BitcoinPriceIntegration.
    
    Attributes:
        coingecko_api_key (str, optional): API key for the CoinGecko Pro API.
    """
    coingecko_api_key: Optional[str] = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"

class BitcoinPriceIntegration(Integration):
    """Integration with Bitcoin price data sources."""
    
    def __init__(self, configuration: BitcoinPriceIntegrationConfiguration):
        super().__init__(configuration)
        self.config = configuration
    
    def get_current_price(self, *args) -> Dict[str, Any]:
        """Get the current Bitcoin price from multiple sources and return a consensus.
        
        Returns:
            Dict[str, Any]: Current price information with metadata.
        """
        # Try Yahoo Finance first
        try:
            btc_data = yf.Ticker("BTC-USD")
            price_info = btc_data.info
            current_price = price_info.get('regularMarketPrice', 0)
            
            if current_price > 0:
                return {
                    "price": float(f"{current_price:.2f}"),
                    "currency": "USD",
                    "source": "Yahoo Finance",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            print(f"Error fetching from Yahoo Finance: {e}")
        
        # Try CoinGecko as backup
        try:
            headers = {"accept": "application/json"}
            if self.config.coingecko_api_key:
                headers["x-cg-pro-api-key"] = self.config.coingecko_api_key
                
            response = requests.get(
                f"{self.config.coingecko_base_url}/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                headers=headers
            )
            data = response.json()
            
            if "bitcoin" in data and "usd" in data["bitcoin"]:
                return {
                    "price": float(f"{data['bitcoin']['usd']:.2f}"),
                    "currency": "USD",
                    "source": "CoinGecko",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            print(f"Error fetching from CoinGecko: {e}")
        
        # Return a fallback message if all sources fail
        return {
            "error": "Unable to fetch current Bitcoin price",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_historical_prices(self, days: int = 30, *args) -> Dict[str, Any]:
        """Get historical Bitcoin prices for charting.
        
        Args:
            days (int): Number of days of historical data to retrieve.
            
        Returns:
            Dict[str, Any]: Historical price data with dates and prices.
        """
        try:
            btc_data = yf.Ticker("BTC-USD")
            hist = btc_data.history(period=f"{days}d")
            
            dates = hist.index.strftime('%Y-%m-%d').tolist()
            prices = [float(f"{price:.2f}") for price in hist['Close'].tolist()]
            
            return {
                "dates": dates,
                "prices": prices,
                "currency": "USD",
                "source": "Yahoo Finance",
                "period_days": days
            }
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return {
                "error": "Unable to fetch historical Bitcoin prices",
                "timestamp": datetime.now().isoformat()
            }
    
    def as_tools(self) -> List[Tool]:
        """Return the tools for the integration.
        
        Returns:
            List[Tool]: List of tools for the integration.
        """
        return [
            Tool(
                name="get_bitcoin_price",
                description="Gets the current Bitcoin price in USD",
                func=self.get_current_price
            ),
            Tool(
                name="get_historical_bitcoin_prices",
                description="Gets historical Bitcoin prices for the specified number of days",
                func=self.get_historical_prices
            )
        ]

# For direct usage
def get_bitcoin_price() -> Dict[str, Any]:
    """Convenience function to get current Bitcoin price without creating integration instance."""
    integration = BitcoinPriceIntegration(BitcoinPriceIntegrationConfiguration())
    return integration.get_current_price()

def get_historical_prices(days: int = 30) -> Dict[str, Any]:
    """Convenience function to get historical Bitcoin prices without creating integration instance."""
    integration = BitcoinPriceIntegration(BitcoinPriceIntegrationConfiguration())
    return integration.get_historical_prices(days)

if __name__ == "__main__":
    # Test the integration
    integration = BitcoinPriceIntegration(BitcoinPriceIntegrationConfiguration())
    
    print("Current Bitcoin price:")
    print(integration.get_current_price())
    
    print("\nHistorical Bitcoin prices (7 days):")
    hist_data = integration.get_historical_prices(7)
    if "error" not in hist_data:
        for i in range(len(hist_data["dates"])):
            print(f"{hist_data['dates'][i]}: ${hist_data['prices'][i]:.2f}") 