"""
Bitcoin Price Providers Test Module

This module compares Bitcoin prices from multiple sources and validates 
the price provided by the Bitcoin agent against a consensus price.
"""

import yfinance as yf
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator
import statistics
from src.custom.bitcoin_agent.agent import create_bitcoin_agent
from src.custom.bitcoin_agent.tests.test_price_validation import (
    extract_price_from_llm_response,
    PriceData,
    get_yahoo_bitcoin_price,
    get_coingecko_bitcoin_price
)

class PriceProvider(BaseModel):
    """Information about a Bitcoin price provider"""
    name: str
    current_price: float
    timestamp: datetime
    currency: str = "USD"
    source_url: str
    
    model_config = {"arbitrary_types_allowed": True}

class ConsensusPriceResult(BaseModel):
    """Consensus price information from multiple providers"""
    providers: List[PriceData]
    consensus_price: float = 0
    std_deviation: float = 0
    min_price: float = 0
    max_price: float = 0
    provider_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @model_validator(mode='after')
    def calculate_statistics(self):
        if self.providers:
            prices = [p.current_price for p in self.providers]
            self.consensus_price = statistics.mean(prices)
            self.std_deviation = statistics.stdev(prices) if len(prices) > 1 else 0
            self.min_price = min(prices)
            self.max_price = max(prices)
            self.provider_count = len(self.providers)
        return self

class AgentConsensusValidation(BaseModel):
    """Validation result comparing agent price to consensus price"""
    consensus: ConsensusPriceResult
    agent_price: float
    agent_response: str
    difference: float = 0
    difference_percentage: float = 0
    is_within_tolerance: bool = False
    tolerance_percentage: float = 5.0
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @model_validator(mode='after')
    def calculate_difference(self):
        if self.agent_price is not None:
            diff = abs(self.consensus.consensus_price - self.agent_price)
            self.difference = diff
            diff_pct = (diff / self.consensus.consensus_price) * 100
            self.difference_percentage = diff_pct
            self.is_within_tolerance = diff_pct <= self.tolerance_percentage
        return self

def get_coinapi_price(api_key: str) -> Optional[PriceData]:
    """Fetch Bitcoin price from CoinAPI"""
    try:
        url = "https://rest.coinapi.io/v1/exchangerate/BTC/USD"
        headers = {"X-CoinAPI-Key": api_key}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'rate' not in data:
            return None
        
        price = data['rate']
        time_str = data.get('time', '')
        timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00')) if time_str else datetime.now()
        
        return PriceData(
            current_price=price,
            timestamp=timestamp,
            currency="USD",
            source="CoinAPI"
        )
    except Exception as e:
        print(f"Error fetching price from CoinAPI: {e}")
        return None

def get_consensus_price() -> ConsensusPriceResult:
    """Get consensus Bitcoin price from multiple providers"""
    providers = []
    
    # Get prices from different providers
    yahoo_price = get_yahoo_bitcoin_price()
    if yahoo_price:
        providers.append(yahoo_price)
    
    coingecko_price = get_coingecko_bitcoin_price()
    if coingecko_price:
        providers.append(coingecko_price)
    
    # Optionally include CoinAPI if API key is available
    # from src import secret
    # if hasattr(secret, 'COINAPI_KEY'):
    #     coinapi_price = get_coinapi_price(secret.COINAPI_KEY)
    #     if coinapi_price:
    #         providers.append(coinapi_price)
    
    # Return consensus result
    return ConsensusPriceResult(providers=providers)

def validate_agent_against_consensus(agent_response: str, tolerance_percentage: float = 5.0) -> AgentConsensusValidation:
    """Validate Bitcoin agent price against consensus from multiple providers"""
    # Get consensus price
    consensus = get_consensus_price()
    
    if not consensus.providers:
        raise ValueError("Could not get price data from any source")
    
    # Extract price from agent response
    try:
        llm_price_data = extract_price_from_llm_response(agent_response)
        agent_price = llm_price_data.current_price
    except ValueError:
        # If extraction fails, set price to None
        agent_price = None
    
    # Return validation result
    return AgentConsensusValidation(
        consensus=consensus,
        agent_price=agent_price,
        agent_response=agent_response,
        tolerance_percentage=tolerance_percentage
    )

def test_agent_consensus_validation():
    """Test that Bitcoin agent price is within acceptable range of consensus"""
    # Create agent
    agent = create_bitcoin_agent()
    
    # Query agent for Bitcoin price
    response = agent.invoke("What is the current Bitcoin price in USD?")
    
    # Validate against consensus
    result = validate_agent_against_consensus(response)
    
    # Print results
    print("\n🔍 Bitcoin Price Providers Consensus Test")
    print(f"Providers ({result.consensus.provider_count}):")
    for provider in result.consensus.providers:
        print(f"  - {provider.source}: ${provider.current_price:.2f} USD ({provider.timestamp.isoformat()})")
    
    print(f"\nConsensus price: ${result.consensus.consensus_price:.2f} USD")
    print(f"Standard deviation: ${result.consensus.std_deviation:.2f}")
    print(f"Range: ${result.consensus.min_price:.2f} - ${result.consensus.max_price:.2f} USD")
    
    print(f"\nAgent price: ${result.agent_price:.2f} USD")
    print(f"Difference: ${result.difference:.2f} ({result.difference_percentage:.2f}%)")
    print(f"Tolerance: {result.tolerance_percentage:.2f}%")
    
    if result.is_within_tolerance:
        print("✅ Agent price is within acceptable range of consensus")
    else:
        print("❌ Agent price exceeds acceptable range of consensus")
    
    # Assert that the price is within tolerance
    assert result.is_within_tolerance, (
        f"Bitcoin price from agent (${result.agent_price:.2f}) "
        f"differs from consensus (${result.consensus.consensus_price:.2f}) "
        f"by {result.difference_percentage:.2f}%, "
        f"which exceeds tolerance of {result.tolerance_percentage:.2f}%"
    )

if __name__ == "__main__":
    try:
        test_agent_consensus_validation()
        print("\n✅ Test passed! Bitcoin agent price matches consensus.")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Error during test: {e}") 