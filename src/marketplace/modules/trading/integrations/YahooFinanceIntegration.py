from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests
import pandas as pd
import time
from typing import List, Dict, Any, Optional
from abi import logger
from src import services
from datetime import datetime
import os
from io import StringIO

@dataclass
class YahooFinanceIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YahooFinance integration.
    
    Attributes:
        user_agent (str): User agent string to use for requests
        max_retries (int): Maximum number of retries for failed requests
        retry_delay (int): Initial retry delay in seconds (will be doubled for each retry)
    """
    datastore_path: str = "datastore/yahoofinance"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    max_retries: int = 3
    retry_delay: int = 1

class YahooFinanceIntegration(Integration):
    """YahooFinance class for interacting with Yahoo Finance data.
    
    This class provides methods to interact with Yahoo Finance's web endpoints.
    It handles fetching historical price data and earnings call information.
    
    Attributes:
        __configuration (YahooFinanceConfiguration): Configuration instance
            containing necessary settings.
    
    Example:
        >>> config = YahooFinanceConfiguration(
        ...     user_agent="Mozilla/5.0 ...",
        ...     max_retries=3,
        ...     retry_delay=1
        ... )
        >>> integration = YahooFinanceIntegration(config)
    """

    __configuration: YahooFinanceIntegrationConfiguration

    def __init__(self, configuration: YahooFinanceIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_table_from_url(self, url: str, output_dir: str, filename: str) -> pd.DataFrame:
        headers = {
            'User-Agent': self.__configuration.user_agent
        }
        
        retry_delay = self.__configuration.retry_delay
        for attempt in range(self.__configuration.max_retries):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                tables = pd.read_html(StringIO(response.text))
                logger.info(f"Found {len(tables)} tables in {url}")

                for i, table in enumerate(tables):
                    data = table.to_csv().encode('utf-8')
                    services.storage_service.put_object(
                        prefix=output_dir,
                        key=filename,
                        content=data,
                    )
                    logger.info(f"Saved table {i} to {os.path.join(output_dir, filename)}")
                    return data
                
            except requests.exceptions.HTTPError as e:
                if attempt == self.__configuration.max_retries - 1:
                    logger.error(f"Failed to fetch historical data after {self.__configuration.max_retries} attempts: {e}")
                    raise
                time.sleep(retry_delay)
                retry_delay *= 2
        
    def get_historical_data(self, symbol: str, period1: int, period2: int, frequency: str = "1d") -> List[Dict[str, Any]]:
        """Get historical price data for a ticker symbol.
        
        Args:
            symbol (str): Ticker symbol (e.g., "AAPL")
            period1 (int): Start timestamp in Unix time
            period2 (int): End timestamp in Unix time
            frequency (str, optional): Data frequency. Defaults to "1d".
                Valid options include "1d" (daily), "1wk" (weekly), "1mo" (monthly).
                
        Returns:
            List[Dict[str, Any]]: Historical price data
            
        Raises:
            requests.exceptions.HTTPError: If the request fails after maximum retries
        """
        # Request URL
        url = f"https://finance.yahoo.com/quote/{symbol}/history/?frequency={frequency}&period1={period1}&period2={period2}"

        # Outputs
        output_dir = os.path.join(self.__configuration.datastore_path, symbol, "historical_data")
        filename = f'{period2}_{period1}_yahoofinance_{symbol}_historical_data_{frequency}.csv'

        try:
            data = services.storage_service.get_object(
                prefix=output_dir,
                key=filename,
            )
            logger.info(f"Historical data found for {symbol} in {output_dir}/{filename}")
            return data
        except Exception as e:
            logger.info(f"No historical data found for {symbol} in {output_dir}/{filename}")

        # Get table from URL
        data = self.get_table_from_url(url, output_dir, filename)
        return data
    
    def get_earnings_calls(self, symbol: str) -> List[Dict[str, Any]]:
        """Get earnings call information for a ticker symbol.
        
        Args:
            symbol (str): Ticker symbol (e.g., "AAPL")
                
        Returns:
            List[Dict[str, Any]]: Earnings call data
            
        Raises:
            requests.exceptions.HTTPError: If the request fails after maximum retries
        """
        # Request URL
        url = f"https://finance.yahoo.com/calendar/earnings/?symbol={symbol}"

        # Outputs
        output_dir = os.path.join(self.__configuration.datastore_path, symbol, "earnings_calls")
        filename = f'{datetime.now().strftime("%Y%m")}_yahoofinance_{symbol}_earnings_calls.csv'

        try:
            data = services.storage_service.get_object(
                prefix=output_dir,
                key=filename,
            )
            logger.info(f"Earnings calls found for {symbol} in {output_dir}/{filename}")
            return data
        except Exception as e:
            logger.info(f"No earnings calls found for {symbol} in {output_dir}/{filename}")
        
        # Get table from URL
        data = self.get_table_from_url(url, output_dir, filename)
        return data