"""
Validation utilities for Bitcoin price data testing.
"""
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union, Tuple

from src.custom.modules.bitcoin.assistants.BitcoinAssistant import create_agent as create_bitcoin_agent
from src.custom.modules.bitcoin.models import ModelConfig, ModelProvider
from src.custom.modules.bitcoin.integrations.BitcoinPriceIntegration import BitcoinPriceIntegration, BitcoinPriceIntegrationConfiguration

@dataclass
class PriceData:
    """Structured Bitcoin price data for validation."""
    price: float
    currency: str = "USD"
    source: str = "Unknown"
    timestamp: Optional[str] = None

def get_bitcoin_price() -> Dict[str, Any]:
    """Get current Bitcoin price using the integration."""
    integration = BitcoinPriceIntegration(BitcoinPriceIntegrationConfiguration())
    return integration.get_current_price()

def get_historical_prices(days: int = 30) -> Dict[str, Any]:
    """Get historical Bitcoin prices using the integration."""
    integration = BitcoinPriceIntegration(BitcoinPriceIntegrationConfiguration())
    return integration.get_historical_prices(days)

def get_yahoo_bitcoin_price() -> PriceData:
    """Get Bitcoin price from Yahoo Finance."""
    # Implementation details...
    return PriceData(price=0.0)

def get_coingecko_bitcoin_price() -> PriceData:
    """Get Bitcoin price from CoinGecko."""
    # Implementation details...
    return PriceData(price=0.0)

def extract_price_from_llm_response(response: str) -> Union[float, None]:
    """Extract a Bitcoin price from an LLM's text response.
    
    Args:
        response: Text response from an LLM that might contain a price
        
    Returns:
        Float price or None if no price could be extracted
    """
    # Look for price patterns like $45,123.45 or 45,123.45 USD
    price_patterns = [
        r'\$([0-9,]+(?:\.[0-9]+)?)',  # $45,123.45
        r'([0-9,]+(?:\.[0-9]+)?)\s*(?:USD|dollars)',  # 45,123.45 USD
        r'(?:USD|dollars)\s*([0-9,]+(?:\.[0-9]+)?)',  # USD 45,123.45
        r'(?:price|worth|value)[^\$0-9]*\$?([0-9,]+(?:\.[0-9]+)?)',  # price is $45,123.45
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            # Clean the matched price (remove commas)
            price_str = match.group(1).replace(',', '')
            try:
                return float(price_str)
            except ValueError:
                continue
    
    return None

def validate_bitcoin_price(price: float, 
                           reference_source: str = "yahoo",
                           tolerance_percent: float = 5.0) -> Tuple[bool, str]:
    """Validate if a Bitcoin price is within tolerance of a reference source.
    
    Args:
        price: The price to validate
        reference_source: Source to compare against ("yahoo" or "coingecko")
        tolerance_percent: Maximum allowed percentage difference
        
    Returns:
        Tuple of (is_valid, validation_message)
    """
    # Get reference price
    if reference_source.lower() == "yahoo":
        reference = get_yahoo_bitcoin_price()
    else:
        reference = get_coingecko_bitcoin_price()
    
    # If reference price is zero, we can't validate
    if reference.price <= 0:
        return False, f"Reference price from {reference_source} is unavailable"
    
    # Calculate percentage difference
    diff_percent = abs(price - reference.price) / reference.price * 100
    
    if diff_percent <= tolerance_percent:
        return True, f"Price ${price} is within {tolerance_percent}% of ${reference.price} from {reference_source}"
    else:
        return False, f"Price ${price} differs by {diff_percent:.2f}% from ${reference.price} ({reference_source})"

def test_bitcoin_agent_price_accuracy(model_config: Optional[ModelConfig] = None) -> Dict[str, Any]:
    """Test if the Bitcoin assistant provides accurate price information.
    
    Args:
        model_config: Optional model configuration for the agent
        
    Returns:
        Dict with test results
    """
    # Create agent with specified model or default
    agent = create_bitcoin_agent(model_config)
    
    # Ask for the current Bitcoin price
    response = agent.invoke("What is the current price of Bitcoin?")
    response_text = response.content
    
    # Extract price from response
    extracted_price = extract_price_from_llm_response(response_text)
    
    # Get reference price for comparison
    reference_data = get_bitcoin_price()
    reference_price = reference_data.get("price", 0)
    
    # Validate the extracted price
    is_valid, validation_message = validate_bitcoin_price(
        extracted_price if extracted_price else 0,
        "API Integration",
        10.0  # Higher tolerance for LLM responses
    )
    
    return {
        "test_name": "Bitcoin Price Accuracy Test",
        "query": "What is the current price of Bitcoin?", 
        "llm_response": response_text,
        "extracted_price": extracted_price,
        "reference_price": reference_price,
        "reference_source": reference_data.get("source", "Unknown"),
        "passed": is_valid,
        "validation_message": validation_message
    }

# Export for use in other modules
__all__ = ['get_bitcoin_price', 'get_historical_prices', 'get_yahoo_bitcoin_price', 
          'get_coingecko_bitcoin_price', 'extract_price_from_llm_response', 
          'validate_bitcoin_price', 'test_bitcoin_agent_price_accuracy',
          'PriceData'] 