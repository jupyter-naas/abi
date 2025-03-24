"""
Tests for Bitcoin price data providers
"""
import unittest
from typing import Dict, Any

from src.custom.modules.bitcoin.assistants.BitcoinAssistant import create_agent as create_bitcoin_agent
from src.custom.modules.bitcoin.tests.test_price_validation import (
    extract_price_from_llm_response,
    PriceData,
    get_bitcoin_price,
    get_yahoo_bitcoin_price,
    get_coingecko_bitcoin_price
)

class TestBitcoinPriceProviders(unittest.TestCase):
    """Test cases for Bitcoin price providers."""
    
    def test_integration_price_provider(self):
        """Test that the integrated price provider returns valid data."""
        price_data = get_bitcoin_price()
        
        # Check if error was returned
        if "error" in price_data:
            self.fail(f"Price provider returned error: {price_data['error']}")
        
        # Validate price data
        self.assertIn("price", price_data, "Price data missing 'price' field")
        self.assertIn("currency", price_data, "Price data missing 'currency' field")
        self.assertIn("timestamp", price_data, "Price data missing 'timestamp' field")
        
        # Price should be a positive number
        self.assertGreater(price_data["price"], 0, "Price should be greater than zero")
        
        # Currency should be USD
        self.assertEqual(price_data["currency"], "USD", "Currency should be USD")
    
    def test_yahoo_price_provider(self):
        """Test the Yahoo Finance price provider."""
        price_data = get_yahoo_bitcoin_price()
        
        # Skip test if price is zero (provider unavailable)
        if price_data.price <= 0:
            self.skipTest("Yahoo Finance price provider unavailable")
        
        # Price should be a positive number
        self.assertGreater(price_data.price, 0, "Yahoo price should be greater than zero")
        
        # Currency should be USD
        self.assertEqual(price_data.currency, "USD", "Yahoo currency should be USD")
    
    def test_coingecko_price_provider(self):
        """Test the CoinGecko price provider."""
        price_data = get_coingecko_bitcoin_price()
        
        # Skip test if price is zero (provider unavailable)
        if price_data.price <= 0:
            self.skipTest("CoinGecko price provider unavailable")
        
        # Price should be a positive number
        self.assertGreater(price_data.price, 0, "CoinGecko price should be greater than zero")
        
        # Currency should be USD
        self.assertEqual(price_data.currency, "USD", "CoinGecko currency should be USD")

if __name__ == "__main__":
    unittest.main() 