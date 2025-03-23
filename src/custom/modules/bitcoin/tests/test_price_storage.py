#!/usr/bin/env python3
"""
Test script for Bitcoin price storage
"""
# Try to import using relative path first (for local execution)
try:
    import sys
    import os
    # Add the parent directory to the path so we can import the modules
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
    from src.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline
except ModuleNotFoundError:
    # If that fails, try importing using the container path structure
    from abi.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline
import json

def test_storage():
    # Initialize the pipeline
    pipeline = BitcoinPricePipeline()
    
    # Display storage path info
    print(f"Storage base path: {pipeline.storage_base_path}")
    print(f"Prices path: {pipeline.prices_path}")
    print(f"Directory exists: {os.path.exists(pipeline.prices_path)}")
    print(f"Directory is writable: {os.access(pipeline.prices_path, os.W_OK)}")
    
    # Get and store the current price
    print("\nGetting current Bitcoin price...")
    result = pipeline.run(store=True)
    print(f"Current price: ${result['current_price']['price']} from {result['current_price']['source']}")
    
    # Force a direct store operation
    print("\nForcing direct storage...")
    pipeline._store_price_data(result['current_price'])
    
    # Check if any files were created
    print("\nChecking for stored data files:")
    if os.path.exists(pipeline.prices_path):
        files = os.listdir(pipeline.prices_path)
        print(f"Files in storage directory: {files}")
        
        if files:
            # Read and display a sample file
            sample_file = os.path.join(pipeline.prices_path, files[0])
            print(f"\nContent of {files[0]}:")
            try:
                with open(sample_file, 'r') as f:
                    data = json.load(f)
                print(json.dumps(data, indent=2))
            except Exception as e:
                print(f"Error reading file: {e}")
    else:
        print("Storage directory does not exist!")

if __name__ == "__main__":
    test_storage() 