#!/usr/bin/env python3
"""
Tests to verify storage functionality for Bitcoin prices
"""
import unittest
import os
import json
from datetime import datetime

class TestStorageVerification(unittest.TestCase):
    """Tests to verify Bitcoin price storage is working correctly."""
    
    def setUp(self):
        """Set up test environment."""
        # Calculate storage path relative to the repository root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.abspath(os.path.join(current_dir, "../../../../.."))
        # Path to the datastore directory
        self.storage_base_path = os.path.join(repo_root, "storage", "datastore")
        self.storage_path = os.path.join(self.storage_base_path, "bitcoin/prices")
        
        print(f"Storage base path: {self.storage_base_path}")
        print(f"Storage prices path: {self.storage_path}")
        
        # Create test files list to clean up later
        self.test_files = []
    
    def tearDown(self):
        """Clean up after tests."""
        # DISABLED CLEANUP to allow file inspection
        print("Test cleanup disabled - files will be preserved for inspection")
        return
        
        # Remove any test files we created
        for test_file in self.test_files:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                    print(f"Removed test file: {test_file}")
                except Exception as e:
                    print(f"Warning: Could not remove test file {test_file}: {e}")
    
    def test_storage_directory_creation(self):
        """Test that storage directories are created as needed."""
        # Create directory if it doesn't exist
        if not os.path.exists(self.storage_path):
            try:
                os.makedirs(self.storage_path, exist_ok=True)
                print(f"Created storage directory: {self.storage_path}")
            except Exception as e:
                self.fail(f"Failed to create storage directory: {e}")
        
        # Directory should exist now
        self.assertTrue(os.path.exists(self.storage_path), 
                      "Storage directory does not exist and couldn't be created")
        
        # Check directory permissions
        self.assertTrue(os.access(self.storage_path, os.W_OK),
                      "Storage directory is not writable")
        self.assertTrue(os.access(self.storage_path, os.R_OK),
                      "Storage directory is not readable")
    
    def test_file_creation_and_read(self):
        """Test that files can be created and read in the storage directory."""
        # Get current date and time
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')  # Date-only folder without Z
        timestamp_str = now.strftime('%Y%m%dT%H%M%S') + 'Z'  # Timestamp with Z suffix
        
        # Create dated folder within prices directory
        dated_folder = os.path.join(self.storage_path, date_str)
        os.makedirs(dated_folder, exist_ok=True)
        print(f"Created or verified dated folder: {dated_folder}")
        
        # Create a sample price data entry
        sample_data = {
            "price": 50000.0,
            "currency": "USD",
            "source": "Test",
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),  # ISO 8601 with Z for UTC
            "last_updated_at": now.timestamp(),  # Unix timestamp (seconds since epoch)
            "market_cap": 950000000000,
            "24h_vol": 28000000000,
            "24h_change": 2.5,
            "provider": "CoinGecko"
        }
        
        # Generate filename with requested format including the currency pair
        filename = f"test_{timestamp_str}_BTCUSD_price.json"
        test_file = os.path.join(dated_folder, filename)
        self.test_files.append(test_file)
        print(f"Attempting to create test file: {test_file}")
        
        # Try to write test file
        try:
            with open(test_file, 'w') as f:
                json.dump([sample_data], f, indent=4)
            print(f"Successfully wrote test file: {test_file}")
        except Exception as e:
            self.fail(f"Failed to write test file: {e}")
        
        # Check if file exists
        file_exists = os.path.exists(test_file)
        print(f"File exists check: {file_exists}")
        self.assertTrue(file_exists, "Test file was not created")
        
        # Try to read the file back
        try:
            with open(test_file, 'r') as f:
                read_data = json.load(f)
            print(f"Successfully read test file: {test_file}")
        except Exception as e:
            self.fail(f"Failed to read test file: {e}")
        
        # Verify data integrity
        self.assertEqual(len(read_data), 1,
                       "Read data should have one item")
        self.assertEqual(read_data[0]["price"], sample_data["price"],
                       "Read price does not match written price")
        
        print(f"Test completed. JSON file should be available at: {test_file}")


if __name__ == "__main__":
    unittest.main() 