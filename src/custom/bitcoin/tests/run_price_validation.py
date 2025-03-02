#!/usr/bin/env python3
"""
Bitcoin Price Validation Test Runner

This script runs the price validation test to compare Bitcoin prices
from the Bitcoin agent against real-time data from Yahoo Finance.
"""

import argparse
from datetime import datetime
import json
import os
from src.custom.bitcoin.tests.test_price_validation import (
    validate_bitcoin_price,
    test_bitcoin_agent_price_accuracy,
    get_bitcoin_price,
    extract_price_from_llm_response
)
from src.custom.bitcoin.agent import create_bitcoin_agent

def run_standalone_test(tolerance: float = 5.0, save_results: bool = False, output_dir: str = None):
    """Run a standalone price validation test and optionally save results"""
    try:
        # Create the agent
        print("Creating Bitcoin agent...")
        agent = create_bitcoin_agent()
        
        # Get Bitcoin price from agent
        print("Querying Bitcoin agent for current price...")
        response = agent.invoke("What is the current Bitcoin price in USD?")
        print(f"Agent response: {response}")
        
        # Validate the price
        print("Validating price against real-time data...")
        validation_result = validate_bitcoin_price(response, tolerance_percentage=tolerance)
        
        # Print detailed results
        print("\n📊 Bitcoin Price Validation Results:")
        print(f"API ({validation_result.api_price.source}): ${validation_result.api_price.current_price:.2f} USD")
        print(f"LLM Response: ${validation_result.llm_price.current_price:.2f} USD")
        print(f"Difference: ${validation_result.price_difference:.2f} ({validation_result.difference_percentage:.2f}%)")
        print(f"Tolerance: {validation_result.tolerance_percentage:.2f}%")
        
        if validation_result.is_within_tolerance:
            print("✅ Price is within acceptable tolerance")
        else:
            print("❌ Price exceeds acceptable tolerance")
        
        # Save results if requested
        if save_results:
            save_validation_results(validation_result, output_dir)
            
        return validation_result
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return None

def save_validation_results(validation_result, output_dir=None):
    """Save validation results to a JSON file"""
    # Create directory if it doesn't exist
    if output_dir is None:
        output_dir = os.path.join("storage", "tests", "bitcoin_price_validation")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"price_validation_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Convert validation result to dict for serialization
    result_dict = {
        "api_price": {
            "current_price": validation_result.api_price.current_price,
            "timestamp": validation_result.api_price.timestamp.isoformat(),
            "currency": validation_result.api_price.currency,
            "source": validation_result.api_price.source
        },
        "llm_price": {
            "current_price": validation_result.llm_price.current_price,
            "timestamp": validation_result.llm_price.timestamp.isoformat(),
            "currency": validation_result.llm_price.currency,
            "extracted_from": validation_result.llm_price.extracted_from
        },
        "price_difference": validation_result.price_difference,
        "difference_percentage": validation_result.difference_percentage,
        "is_within_tolerance": validation_result.is_within_tolerance,
        "tolerance_percentage": validation_result.tolerance_percentage
    }
    
    # Save to file
    with open(filepath, "w") as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"Results saved to {filepath}")
    return filepath

def main():
    """Main function to run the price validation test from command line"""
    parser = argparse.ArgumentParser(description="Validate Bitcoin price from agent against real-time data")
    parser.add_argument("--tolerance", type=float, default=5.0, 
                        help="Tolerance percentage for price discrepancy (default: 5.0)")
    parser.add_argument("--save", action="store_true", 
                        help="Save validation results to a file")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directory to save results (default: storage/tests/bitcoin_price_validation)")
    
    args = parser.parse_args()
    
    print("🔍 Running Bitcoin Price Validation Test")
    print(f"Tolerance: {args.tolerance}%")
    print(f"Save results: {'Yes' if args.save else 'No'}")
    if args.save and args.output_dir:
        print(f"Output directory: {args.output_dir}")
    
    result = run_standalone_test(args.tolerance, args.save, args.output_dir)
    
    if result and result.is_within_tolerance:
        print("\n✅ Test passed! Bitcoin agent price is accurate.")
        return 0
    else:
        print("\n❌ Test failed! Bitcoin agent price exceeds tolerance.")
        return 1

if __name__ == "__main__":
    exit(main()) 