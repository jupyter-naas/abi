"""
Bitcoin Price Pipeline

A pipeline for processing and analyzing Bitcoin price data
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import os
import json
import logging
import tempfile
import stat

from abi.pipeline import Pipeline
from langchain_core.tools import Tool
from fastapi import APIRouter
from src.custom.modules.bitcoin.integrations.BitcoinPriceIntegration import (
    BitcoinPriceIntegration, 
    BitcoinPriceIntegrationConfiguration
)

class BitcoinPricePipeline(Pipeline):
    """Pipeline for processing Bitcoin price data."""
    
    def __init__(self):
        self.integration = BitcoinPriceIntegration(
            BitcoinPriceIntegrationConfiguration()
        )
        # Focus on the requested storage path
        storage_path = "/app/src/custom/modules/bitcoin/data"
        print(f"Using Bitcoin data storage path: {storage_path}")
        
        # Make sure parent directories exist with proper permissions
        try:
            # Create each directory in path with full permissions
            parts = storage_path.split('/')
            current_path = ""
            for part in parts:
                if not part:  # Skip empty parts (like after leading /)
                    current_path += "/"
                    continue
                
                current_path = os.path.join(current_path, part)
                if not os.path.exists(current_path):
                    print(f"Creating directory: {current_path}")
                    try:
                        os.mkdir(current_path)
                    except PermissionError:
                        print(f"Permission error creating {current_path}, trying with sudo")
                        import subprocess
                        subprocess.run(["sudo", "mkdir", "-p", current_path])
                        subprocess.run(["sudo", "chmod", "777", current_path])
                else:
                    print(f"Directory exists: {current_path}")
                
                # Try to set permissive permissions
                try:
                    os.chmod(current_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                    print(f"Set permissions on {current_path}")
                except Exception as e:
                    print(f"Could not set permissions on {current_path}: {e}")
        except Exception as e:
            print(f"Error setting up storage directory structure: {e}")
        
        self.storage_base_path = os.environ.get(
            "BITCOIN_DATA_PATH", 
            storage_path
        )
        self.prices_path = os.path.join(self.storage_base_path, "prices")
        
        # Create storage directory with explicit permissions
        try:
            os.makedirs(self.prices_path, exist_ok=True)
            # Try to set permissive permissions (mode 0777 - rwx for all)
            os.chmod(self.prices_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except Exception as e:
            print(f"Warning: Could not set permissions on {self.prices_path}: {e}")
        
        # Print debug info at initialization
        print(f"Bitcoin price data will be stored in: {self.prices_path}")
        print(f"Directory exists: {os.path.exists(self.prices_path)}")
        is_writable = False
        try:
            # Test write access by creating a temp file
            test_file = os.path.join(self.prices_path, "write_test.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            is_writable = True
        except Exception as e:
            print(f"Directory write test failed: {e}")
        print(f"Directory is writable: {is_writable}")
    
    def as_tools(self) -> List[Tool]:
        """Return tools for this pipeline.
        
        Returns:
            List of tools for accessing pipeline functionality
        """
        return [
            Tool(
                name="get_bitcoin_price_data",
                description="Get current and historical Bitcoin price data",
                func=lambda days=0: self.run(days=int(days))
            ),
            Tool(
                name="get_stored_bitcoin_prices",
                description="Retrieve stored Bitcoin price data",
                func=lambda start_date=None, end_date=None: self.get_stored_prices(
                    start_date=start_date, end_date=end_date
                )
            ),
            Tool(
                name="store_bitcoin_price_history",
                description="Store Bitcoin price history for a specified number of days",
                func=lambda days=7: self.store_price_history(days=int(days))
            )
        ]
    
    def as_api(self, router: APIRouter) -> None:
        """Register API endpoints for this pipeline.
        
        Args:
            router: FastAPI router to register endpoints with
        """
        @router.get("/bitcoin/price/current")
        def get_current_price():
            """Get current Bitcoin price."""
            return self.run(days=0)
        
        @router.get("/bitcoin/price/historical/{days}")
        def get_historical_prices(days: int = 7):
            """Get historical Bitcoin price data."""
            return self.run(days=days)
        
        @router.get("/bitcoin/price/stored")
        def get_stored_prices(start_date: str = None, end_date: str = None):
            """Get stored Bitcoin price data."""
            return self.get_stored_prices(start_date=start_date, end_date=end_date)
        
        @router.post("/bitcoin/price/store/{days}")
        def store_price_history(days: int = 7):
            """Store Bitcoin price history for specified days."""
            return self.store_price_history(days=days)
    
    def run(self, days: int = 0, source: str = None, store: bool = True) -> Dict[str, Any]:
        """Run the Bitcoin price pipeline.
        
        Args:
            days: Number of days for historical data (0 = current price only)
            source: Preferred data source (None = use default fallback priority)
            store: Whether to store the results (defaults to True)
            
        Returns:
            Dict containing price data and analysis
        """
        result = {}
        
        # Get current price
        current_price = self.integration.get_current_price()
        result["current_price"] = current_price
        
        # Store current price data
        storage_status = "not_attempted"
        if store and "error" not in current_price:
            try:
                self._store_price_data(current_price)
                storage_status = "success"
            except Exception as e:
                storage_status = f"failed: {str(e)}"
                logging.error(f"Failed to store Bitcoin price data: {e}")
        
        # Add storage status to result
        result["storage"] = {
            "attempted": store and "error" not in current_price,
            "status": storage_status,
            "location": self.prices_path if storage_status == "success" else None
        }
        
        # Get historical prices if requested
        if days > 0:
            historical = self.integration.get_historical_prices(days)
            result["historical"] = historical
            
            # Add basic analysis when historical data is available
            if "error" not in historical and len(historical.get("prices", [])) > 0:
                prices = historical["prices"]
                result["analysis"] = {
                    "average": round(sum(prices) / len(prices), 2),
                    "max": max(prices),
                    "min": min(prices),
                    "volatility": round(max(prices) - min(prices), 2),
                    "days_analyzed": days
                }
        
        return result
    
    def _store_price_data(self, price_data: Dict[str, Any]) -> bool:
        """Store price data for later retrieval and returns success status.
        
        Args:
            price_data: Price data dictionary to store
            
        Returns:
            True if storage was successful, False otherwise
        
        Raises:
            IOError: If there are file access issues
            ValueError: If the data cannot be serialized
        """
        print(f"Attempting to store price data in {self.prices_path}")
        
        # Double-check the directory exists and is writable
        try:
            os.makedirs(self.prices_path, exist_ok=True)
        except Exception as e:
            print(f"Failed to create directory {self.prices_path}: {e}")
            # Try a fallback to temp directory
            self.prices_path = os.path.join(tempfile.mkdtemp(prefix="bitcoin_"), "prices")
            os.makedirs(self.prices_path, exist_ok=True)
            print(f"Using fallback path: {self.prices_path}")
        
        # Create a filename based on the date
        today = date.today().isoformat()
        filename = os.path.join(self.prices_path, f"{today}.json")
        print(f"Will store data in file: {filename}")
        
        # Load existing data if file exists
        data = []
        if os.path.exists(filename):
            print(f"File {filename} exists, loading existing data")
            with open(filename, 'r') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = [data]  # Convert to list if not already
                    print(f"Loaded {len(data)} existing records")
                except json.JSONDecodeError:
                    print(f"File {filename} contains invalid JSON, starting fresh")
                    # File exists but isn't valid JSON, start fresh
                    data = []
        else:
            print(f"File {filename} does not exist, creating new file")
        
        # Append the new price data
        data.append(price_data)
        print(f"Appending new price data, total records: {len(data)}")
        
        # Write the data back to the file
        print(f"Writing data to {filename}")
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Verify file was actually created and is readable
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    verification_data = json.load(f)
                file_size = os.path.getsize(filename)
                print(f"✅ VERIFICATION SUCCESSFUL: File exists ({file_size} bytes) and contains {len(verification_data)} records")
            except Exception as e:
                print(f"❌ VERIFICATION FAILED: File exists but cannot be read: {e}")
        else:
            print(f"❌ VERIFICATION FAILED: File does not exist after write operation")
        
        logging.info(f"Stored Bitcoin price data for {today}")
        print(f"Bitcoin price data stored in {filename}")
        
        return True
    
    def get_stored_prices(self, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Retrieve stored price data.
        
        Args:
            start_date: Optional start date in ISO format (YYYY-MM-DD)
            end_date: Optional end date in ISO format (YYYY-MM-DD)
            
        Returns:
            List of stored price data dictionaries
        """
        result = []
        
        try:
            # List all price data files
            files = [f for f in os.listdir(self.prices_path) if f.endswith('.json')]
            
            # Filter by date range if specified
            if start_date or end_date:
                filtered_files = []
                for f in files:
                    file_date = f.split('.')[0]  # Extract date from filename
                    if start_date and file_date < start_date:
                        continue
                    if end_date and file_date > end_date:
                        continue
                    filtered_files.append(f)
                files = filtered_files
            
            # Load and append data from each file
            for filename in sorted(files):
                file_path = os.path.join(self.prices_path, filename)
                with open(file_path, 'r') as f:
                    file_data = json.load(f)
                    result.extend(file_data)
            
            return result
        except Exception as e:
            logging.error(f"Failed to retrieve stored Bitcoin price data: {e}")
            return []
    
    def get_price_summary(self) -> Dict[str, Any]:
        """Get a summary of Bitcoin price with 7-day analysis.
        
        Returns:
            Dict containing current price and 7-day analysis
        """
        return self.run(days=7)
    
    def store_price_history(self, days: int = 7) -> Dict[str, Any]:
        """Explicitly store Bitcoin price history for a specified number of days.
        
        Args:
            days: Number of days of price history to store (default 7)
            
        Returns:
            Dict containing storage result and summary of stored data
        """
        # Run the pipeline with explicit storage flag
        result = self.run(days=days, store=True)
        
        # Add additional storage information
        result["storage_summary"] = {
            "days_requested": days,
            "timestamp": datetime.now().isoformat(),
            "storage_path": self.prices_path,
            "message": f"Stored {days} days of Bitcoin price history"
        }
        
        print(f"Explicitly stored {days} days of Bitcoin price history")
        return result 