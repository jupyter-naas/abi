"""
Bitcoin Price Validation Test Module

This module tests the accuracy of Bitcoin price information provided by the Bitcoin agent
by comparing it with real-time data from Yahoo Finance.
"""

import yfinance as yf
import requests
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List, Tuple
from pydantic import BaseModel, Field, model_validator
import pytest
from src.custom.bitcoin.agent import create_bitcoin_agent
from src.custom.bitcoin.models import ModelConfig, ModelProvider

# Pydantic models for price validation
class PriceData(BaseModel):
    """Price data from an API source"""
    current_price: float = Field(..., description="Current Bitcoin price in USD")
    timestamp: datetime = Field(..., description="When the price was fetched")
    currency: str = Field("USD", description="Currency of the price")
    source: str = Field(..., description="Source of the price data")
    
    @model_validator(mode='after')
    def validate_price(self):
        if self.current_price <= 0:
            raise ValueError("Price must be positive")
        return self

class LLMPriceData(BaseModel):
    """Price data extracted from LLM response"""
    current_price: float = Field(..., description="Current Bitcoin price extracted from LLM response")
    timestamp: datetime = Field(..., description="When the response was generated")
    currency: str = Field("USD", description="Currency of the price")
    extracted_from: str = Field(..., description="The original text from which price was extracted")
    
    @model_validator(mode='after')
    def validate_price(self):
        if self.current_price <= 0:
            raise ValueError("Price must be positive")
        return self

class PriceValidationResult(BaseModel):
    """Result of price validation between API and LLM data"""
    api_price: PriceData
    llm_price: LLMPriceData
    price_difference: float = 0
    difference_percentage: float = 0
    is_within_tolerance: bool = False
    tolerance_percentage: float = Field(5.0, description="Tolerance percentage for price discrepancy")
    
    @model_validator(mode='after')
    def calculate_difference(self):
        price_diff = abs(self.api_price.current_price - self.llm_price.current_price)
        self.price_difference = price_diff
        
        # Calculate percentage difference
        diff_percentage = (price_diff / self.api_price.current_price) * 100
        self.difference_percentage = diff_percentage
        
        # Check if within tolerance
        self.is_within_tolerance = diff_percentage <= self.tolerance_percentage
        
        return self

# Functions to fetch and validate prices
def get_yahoo_bitcoin_price() -> Optional[PriceData]:
    """
    Fetch the current Bitcoin price from Yahoo Finance
    
    Returns:
        PriceData: Current Bitcoin price data or None if failed
    """
    try:
        # Try to get Bitcoin price data from Yahoo Finance
        btc_ticker = yf.Ticker("BTC-USD")
        btc_data = btc_ticker.history(period="1d")
        
        if btc_data.empty:
            return None
        
        # Get the most recent closing price
        latest_price = btc_data['Close'].iloc[-1]
        
        return PriceData(
            current_price=latest_price,
            timestamp=datetime.now(),
            currency="USD",
            source="Yahoo Finance"
        )
    except Exception as e:
        print(f"Error fetching price from Yahoo Finance: {e}")
        return None

def get_coingecko_bitcoin_price() -> Optional[PriceData]:
    """
    Fetch the current Bitcoin price from CoinGecko
    
    Returns:
        PriceData: Current Bitcoin price data or None if failed
    """
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_last_updated_at=true"
        response = requests.get(url)
        data = response.json()
        
        if 'bitcoin' not in data:
            return None
        
        price = data['bitcoin']['usd']
        last_updated = datetime.fromtimestamp(data['bitcoin'].get('last_updated_at', time.time()))
        
        return PriceData(
            current_price=price,
            timestamp=last_updated,
            currency="USD",
            source="CoinGecko"
        )
    except Exception as e:
        print(f"Error fetching price from CoinGecko: {e}")
        return None

def get_bitcoin_price() -> PriceData:
    """
    Get Bitcoin price from available sources with fallbacks
    
    Returns:
        PriceData: Current Bitcoin price data
        
    Raises:
        ValueError: If unable to get price from any source
    """
    # Try Yahoo Finance first
    price_data = get_yahoo_bitcoin_price()
    if price_data:
        print(f"Got Bitcoin price from Yahoo Finance: ${price_data.current_price:.2f}")
        return price_data
    
    # Fall back to CoinGecko
    price_data = get_coingecko_bitcoin_price()
    if price_data:
        print(f"Got Bitcoin price from CoinGecko: ${price_data.current_price:.2f}")
        return price_data
    
    # If all sources fail, raise an error
    raise ValueError("Failed to fetch Bitcoin price from any source")

def extract_price_from_llm_response(response: str) -> LLMPriceData:
    """
    Extract Bitcoin price information from an LLM response
    
    Args:
        response: Text response from the LLM containing price information
        
    Returns:
        LLMPriceData: Extracted price data
    
    Raises:
        ValueError: If no price could be extracted
    """
    # Pattern to match price values like $45,123.45 or 45,123.45 USD
    price_pattern = r'[$£€]?\s?([0-9,]+(?:\.[0-9]+)?)\s?(?:USD|dollars|EUR|euros|GBP|pounds)?'
    
    # Find all potential price matches
    matches = re.findall(price_pattern, response)
    
    if not matches:
        raise ValueError(f"Could not extract price from response: {response}")
    
    # Process the first match (most likely to be the Bitcoin price)
    # Remove commas and convert to float
    price_str = matches[0].replace(',', '')
    price = float(price_str)
    
    return LLMPriceData(
        current_price=price,
        timestamp=datetime.now(),
        currency="USD",
        extracted_from=response
    )

def validate_bitcoin_price(llm_response: str, tolerance_percentage: float = 5.0) -> PriceValidationResult:
    """
    Validate Bitcoin price from LLM against real-time price data
    
    Args:
        llm_response: The text response from the LLM containing Bitcoin price
        tolerance_percentage: Acceptable difference percentage (default 5%)
        
    Returns:
        PriceValidationResult: Validation result with comparison details
    """
    # Get price from API
    api_price = get_bitcoin_price()
    
    # Extract price from LLM response
    llm_price = extract_price_from_llm_response(llm_response)
    
    # Return validation result
    return PriceValidationResult(
        api_price=api_price,
        llm_price=llm_price,
        tolerance_percentage=tolerance_percentage
    )

# Test function to verify Bitcoin agent price against Yahoo Finance
def test_bitcoin_agent_price_accuracy():
    """
    Test that the Bitcoin agent provides accurate price information
    compared to real-time price data.
    """
    # Create Bitcoin agent
    agent = create_bitcoin_agent()
    
    # Ask for current Bitcoin price
    response = agent.invoke("What is the current Bitcoin price in USD?")
    
    # Validate the price
    validation_result = validate_bitcoin_price(response)
    
    # Print detailed results
    print(f"\nBitcoin Price Validation Results:")
    print(f"API ({validation_result.api_price.source}): ${validation_result.api_price.current_price:.2f} USD")
    print(f"LLM Response: ${validation_result.llm_price.current_price:.2f} USD")
    print(f"Difference: ${validation_result.price_difference:.2f} ({validation_result.difference_percentage:.2f}%)")
    print(f"Tolerance: {validation_result.tolerance_percentage:.2f}%")
    print(f"Within tolerance: {'✅' if validation_result.is_within_tolerance else '❌'}")
    
    # Assert that the price is within tolerance
    assert validation_result.is_within_tolerance, (
        f"Bitcoin price from agent (${validation_result.llm_price.current_price:.2f}) "
        f"differs from {validation_result.api_price.source} (${validation_result.api_price.current_price:.2f}) "
        f"by {validation_result.difference_percentage:.2f}%, "
        f"which exceeds tolerance of {validation_result.tolerance_percentage:.2f}%"
    )

if __name__ == "__main__":
    # Run the test manually if script is executed directly
    try:
        test_bitcoin_agent_price_accuracy()
        print("\n✅ Test passed! Bitcoin agent price is accurate.")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Error during test: {e}") 