"""
Tests for Bitcoin Price Pipeline
"""
import unittest
from src.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline

class TestBitcoinPricePipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = BitcoinPricePipeline()
    
    def test_current_price(self):
        """Test that the pipeline returns current price data."""
        result = self.pipeline.run()
        self.assertIn("current_price", result)
        self.assertIsInstance(result["current_price"], dict)
        
        # If no errors, price should be present
        if "error" not in result["current_price"]:
            self.assertIn("price", result["current_price"])
            self.assertIn("currency", result["current_price"])
    
    def test_historical_analysis(self):
        """Test that the pipeline returns historical analysis."""
        days = 7
        result = self.pipeline.run(days=days)
        
        self.assertIn("historical", result)
        
        # If we got historical data, check analysis
        if "error" not in result.get("historical", {}):
            self.assertIn("analysis", result)
            self.assertIn("average", result["analysis"])
            self.assertIn("max", result["analysis"])
            self.assertIn("min", result["analysis"])
            self.assertIn("volatility", result["analysis"])
            self.assertEqual(result["analysis"]["days_analyzed"], days)

    def test_data_storage(self):
        """Test storing and retrieving price data."""
        # Run pipeline with storage
        self.pipeline.run(store=True)
        
        # Retrieve stored data
        stored_data = self.pipeline.get_stored_prices()
        
        # Verify we have at least one stored price entry
        self.assertGreater(len(stored_data), 0)
        
        # Verify the stored data structure
        if stored_data:
            self.assertIn("price", stored_data[0])
            self.assertIn("currency", stored_data[0])
            self.assertIn("timestamp", stored_data[0])

if __name__ == "__main__":
    unittest.main() 