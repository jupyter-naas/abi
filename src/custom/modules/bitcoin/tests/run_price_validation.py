"""
Test runner for Bitcoin price validation tests
"""
import unittest
import sys
from argparse import ArgumentParser

from src.custom.modules.bitcoin.tests.test_price_validation import (
    validate_bitcoin_price,
    test_bitcoin_agent_price_accuracy,
    get_bitcoin_price,
    extract_price_from_llm_response
)
from src.custom.modules.bitcoin.assistants.BitcoinAssistant import create_agent as create_bitcoin_agent
from src.custom.modules.bitcoin.models import ModelConfig, ModelProvider

def run_validation_tests(verbose=False):
    """Run Bitcoin price validation tests."""
    print("Running Bitcoin Price Validation Tests")
    print("=====================================")
    
    # Get current price for reference
    price_data = get_bitcoin_price()
    if "error" in price_data:
        print(f"Error: {price_data['error']}")
        return False
    
    print(f"Current Bitcoin price: ${price_data['price']} ({price_data['source']})")
    
    # Test agent price accuracy
    print("\nTesting Bitcoin agent price accuracy...")
    test_result = test_bitcoin_agent_price_accuracy()
    
    print(f"Query: {test_result['query']}")
    if verbose:
        print(f"Response: {test_result['llm_response']}")
    print(f"Extracted price: ${test_result['extracted_price']}")
    print(f"Reference price: ${test_result['reference_price']} ({test_result['reference_source']})")
    print(f"Result: {'✅ PASSED' if test_result['passed'] else '❌ FAILED'}")
    print(f"Details: {test_result['validation_message']}")
    
    return test_result['passed']

if __name__ == "__main__":
    parser = ArgumentParser(description="Bitcoin Price Validation Test Runner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()
    
    success = run_validation_tests(verbose=args.verbose)
    sys.exit(0 if success else 1) 