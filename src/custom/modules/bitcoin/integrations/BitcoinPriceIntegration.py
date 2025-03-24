"""
Bitcoin Price Integration

Provides integration with Bitcoin price data sources like Yahoo Finance and CoinGecko.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
import yfinance as yf
import requests
import logging

from langchain_core.tools import Tool

# Base classes for integration pattern
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
    
    def get_current_price(self, store: bool = True) -> Dict[str, Any]:
        """Get current Bitcoin price from available sources.
        
        Args:
            store: Whether to store the price data (requires pipeline to be initialized)
            
        Returns:
            Dict with price data or error message
        """
        # Get price from providers
        price_data = self._get_price_from_providers()
        
        # Ensure the price is displayed with proper formatting in the agent response
        if "price" in price_data and "price_formatted" in price_data:
            # Create a copy to avoid modifying the data we'll store
            display_data = price_data.copy()
            # Add formatted price as a separate field for the agent to use
            display_data["display_price"] = f"${price_data['price_formatted']}"
            
            # If store flag is True and we're connected to a pipeline, store the data
            if store and hasattr(self, '_pipeline'):
                try:
                    self._pipeline._store_price_data(price_data)
                except Exception as e:
                    logging.warning(f"Failed to store price data: {e}")
            
            return display_data
        
        return price_data
    
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

    def _get_price_from_providers(self) -> Dict[str, Any]:
        """Get the current Bitcoin price from multiple sources and return a consensus."""
        # Try Yahoo Finance first
        try:
            btc_data = yf.Ticker("BTC-USD")
            price_info = btc_data.info
            current_price = price_info.get('regularMarketPrice', 0)
            
            if current_price > 0:
                # Format price with commas and 2 decimal places (no $ sign)
                return {
                    "price": current_price,
                    "price_formatted": f"{current_price:,.2f}",
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
                
            # Request the price with full precision
            response = requests.get(
                f"{self.config.coingecko_base_url}/simple/price",
                params={
                    "ids": "bitcoin", 
                    "vs_currencies": "usd",
                    "precision": "full"  # Request full precision
                },
                headers=headers
            )
            data = response.json()
            
            if "bitcoin" in data and "usd" in data["bitcoin"]:
                btc_price = data['bitcoin']['usd']
                print(f"Raw API price: {btc_price} (type: {type(btc_price).__name__})")
                
                # Format price with commas and 2 decimal places (no $ sign)
                formatted_price = f"{btc_price:,.2f}"
                print(f"Formatted price: {formatted_price}")
                
                return {
                    "price": btc_price,
                    "price_formatted": formatted_price,
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