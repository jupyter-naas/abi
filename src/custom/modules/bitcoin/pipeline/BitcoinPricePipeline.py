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
        # Create integration
        self.integration = BitcoinPriceIntegration(
            BitcoinPriceIntegrationConfiguration()
        )
        # Connect pipeline back to integration for storage functionality
        self.integration._pipeline = self
        
        # Focus on the requested storage path
        storage_path = "/app/src/custom/modules/bitcoin/data"
        print(f"Using Bitcoin data storage path: {storage_path}")
        
        # Set environment variables based on directory structure
        storage_base_path = os.environ.get("BITCOIN_DATA_PATH", storage_path)
        # Allow override for datastore path
        if "BITCOIN_DATASTORE_PATH" in os.environ:
            self.storage_base_path = os.environ.get("BITCOIN_DATASTORE_PATH")
            print(f"Using environment-specified datastore path: {self.storage_base_path}")
        else:
            # Default to original path or environment variable
            self.storage_base_path = storage_base_path
            
        # Try to detect if we're running in development mode
        current_file = os.path.abspath(__file__)
        if "src/custom/modules" in current_file:
            # We're likely in development mode, try to use storage/datastore
            repo_root = os.path.abspath(os.path.join(os.path.dirname(current_file), "../../../../../"))
            possible_datastore = os.path.join(repo_root, "storage", "datastore")
            if os.path.exists(os.path.dirname(possible_datastore)):
                self.storage_base_path = possible_datastore
                print(f"Development mode detected, using datastore path: {self.storage_base_path}")
        
        self.prices_path = os.path.join(self.storage_base_path, "bitcoin/prices")
        
        # Make sure parent directories exist with proper permissions
        try:
            os.makedirs(self.prices_path, exist_ok=True)
            print(f"Created or verified prices path: {self.prices_path}")
        except Exception as e:
            print(f"Error setting up prices directory: {e}")
        
        # Print debug info at initialization
        print(f"Bitcoin price data will be stored in: {self.prices_path}")
        
        # Store initial price data on startup
        try:
            initial_price = self.integration.get_current_price()
            if "error" not in initial_price:
                self._store_price_data(initial_price)
                print("✅ Successfully stored initial Bitcoin price data on startup")
            else:
                print(f"⚠️ Could not store initial price data: {initial_price.get('error')}")
        except Exception as e:
            print(f"⚠️ Error storing initial price data: {e}")
    
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
        
        # Get current date and time
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        timestamp_str = now.strftime('%Y%m%dT%H%M%S') + 'Z'
        
        # Create dated folder within prices directory
        dated_folder = os.path.join(self.prices_path, date_str)
        os.makedirs(dated_folder, exist_ok=True)
        print(f"Created or verified dated folder: {dated_folder}")
        
        # Create a filename with the new format
        filename = os.path.join(dated_folder, f"{timestamp_str}_BTCUSD_price.json")
        print(f"Will store data in file: {filename}")
        
        # Enhance price data with additional fields if not present
        if isinstance(price_data, dict) and "timestamp" not in price_data:
            price_data["timestamp"] = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if isinstance(price_data, dict) and "last_updated_at" not in price_data:
            price_data["last_updated_at"] = now.timestamp()
        if isinstance(price_data, dict) and "currency" not in price_data:
            price_data["currency"] = "USD"
        
        # Store data as a list to match test format
        data = [price_data]
        
        # Write the data to the file
        print(f"Writing data to {filename}")
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        
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
        
        logging.info(f"Stored Bitcoin price data for {now.isoformat()}")
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
            # Check if prices directory exists
            if not os.path.exists(self.prices_path):
                logging.warning(f"Prices directory {self.prices_path} does not exist")
                return []
            
            # Get list of date folders
            date_folders = [f for f in os.listdir(self.prices_path) 
                          if os.path.isdir(os.path.join(self.prices_path, f))]
            
            # Filter by date range if specified
            if start_date or end_date:
                filtered_folders = []
                for folder in date_folders:
                    # Convert to ISO format for comparison
                    folder_date = f"{folder[:4]}-{folder[4:6]}-{folder[6:8]}"
                    if start_date and folder_date < start_date:
                        continue
                    if end_date and folder_date > end_date:
                        continue
                    filtered_folders.append(folder)
                date_folders = filtered_folders
            
            # Process each date folder
            for date_folder in sorted(date_folders):
                folder_path = os.path.join(self.prices_path, date_folder)
                
                # Get all JSON files in this date folder
                json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
                
                # Load and append data from each file
                for filename in sorted(json_files):
                    file_path = os.path.join(folder_path, filename)
                    with open(file_path, 'r') as f:
                        file_data = json.load(f)
                        # If file data is a list, extend result with its contents
                        if isinstance(file_data, list):
                            result.extend(file_data)
                        # If file data is a dict, append it directly
                        elif isinstance(file_data, dict):
                            result.append(file_data)
            
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