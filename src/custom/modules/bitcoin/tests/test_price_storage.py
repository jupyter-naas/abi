#!/usr/bin/env python3
"""
Tests for Bitcoin price storage functionality
"""
import unittest
import os
import json
import tempfile
from datetime import datetime
from typing import Dict, Any

from src.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline
from src.custom.modules.bitcoin.integrations.BitcoinPriceIntegration import BitcoinPriceIntegration, BitcoinPriceIntegrationConfiguration

class TestBitcoinPriceStorage(unittest.TestCase):
    """Test cases for Bitcoin price storage functionality."""
    
    def setUp(self):
        """Set up test environment with temporary storage location."""
        # Create a temporary directory for test storage
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Initialize the pipeline with the temp directory
        self.pipeline = BitcoinPricePipeline(storage_base_path=self.temp_dir.name)
        
        # Create a sample price data entry
        self.sample_price_data = {
            "price": 45000.0,
            "currency": "USD",
            "source": "Test",
            "timestamp": datetime.now().isoformat()
        }
    
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
    
    def test_storage_directories_created(self):
        """Test that storage directories are created correctly."""
        # The pipeline should create directories as needed
        self.pipeline.run(store=True)
        
        # Check if the price directory exists
        self.assertTrue(os.path.exists(self.pipeline.prices_path), 
                      "Price storage directory was not created")
        
        # Check directory permissions
        self.assertTrue(os.access(self.pipeline.prices_path, os.W_OK),
                      "Price storage directory is not writable")
    
    def test_store_price_data(self):
        """Test storing price data and retrieving it."""
        # Store the sample price data
        self.pipeline._store_price_data(self.sample_price_data)
        
        # Get stored prices
        stored_prices = self.pipeline.get_stored_prices()
        
        # Verify at least one price is stored
        self.assertGreaterEqual(len(stored_prices), 1,
                             "No price data was stored")
        
        # Verify the stored data matches what we put in
        self.assertEqual(stored_prices[0]["price"], self.sample_price_data["price"],
                      "Stored price does not match sample price")
        self.assertEqual(stored_prices[0]["currency"], self.sample_price_data["currency"],
                      "Stored currency does not match sample currency")
    
    def test_pipeline_with_storage(self):
        """Test the full pipeline with storage enabled."""
        # Run the pipeline with storage
        result = self.pipeline.run(store=True)
        
        # Check if the pipeline returned current price data
        self.assertIn("current_price", result,
                    "Pipeline did not return current price data")
        
        # Verify stored data exists
        stored_prices = self.pipeline.get_stored_prices()
        self.assertGreaterEqual(len(stored_prices), 1,
                             "Pipeline did not store any price data")
        
        # Verify stored data structure
        for price_entry in stored_prices:
            self.assertIn("price", price_entry, "Stored price entry missing 'price' field")
            self.assertIn("currency", price_entry, "Stored price entry missing 'currency' field")
            self.assertIn("timestamp", price_entry, "Stored price entry missing 'timestamp' field")

if __name__ == "__main__":
    unittest.main() 