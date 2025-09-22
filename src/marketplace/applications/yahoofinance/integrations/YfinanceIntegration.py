from typing import Dict, List, Any
import yfinance as yf # type: ignore
from yahooquery import search # type: ignore
import pandas as pd # type: ignore
from dataclasses import dataclass
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
import os
from src.utils.Storage import save_json
from abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
import datetime
from abi import logger

cache = CacheFactory.CacheFS_find_storage(subpath="yahoofinance")

@dataclass
class YfinanceIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Yahoo Finance integration.
    
    Attributes:
        data_store_path (str): Path to store cached financial data
    """
    data_store_path: str = "datastore/yahoofinance/yfinance"

class YfinanceIntegration(Integration):
    """Yahoo Finance integration client for financial data retrieval.
    
    This class provides methods to interact with Yahoo Finance API endpoints
    for retrieving stock, sector, and industry information.
    
    Attributes:
        __configuration (YfinanceIntegrationConfiguration): Configuration instance
            containing necessary settings for data storage.
    
    Example:
        >>> config = YfinanceIntegrationConfiguration(
        ...     data_store_path="datastore/yahoofinance/yfinance"
        ... )
        >>> integration = YfinanceIntegration(config)
    """

    __configuration: YfinanceIntegrationConfiguration

    def __init__(self, configuration: YfinanceIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _result_df_to_dict(self, result: pd.DataFrame) -> List[Dict]:
        """Convert DataFrame to dictionary format with proper indexing.
        
        Args:
            result (pd.DataFrame): DataFrame to convert
            
        Returns:
            List[Dict]: List of dictionaries representing DataFrame rows
        """
        if result is None or result.empty:
            return []
            
        df = pd.DataFrame(result)
        
        # Convert index to string if it's a timestamp
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = df.index.strftime('%Y-%m-%dT%H:%M:%S%z')
        
        # Create index from name column
        df.insert(0, 'key', df.index)
        df = df.fillna(0)
        
        # Clean column names
        for column in df.columns:
            if isinstance(column, pd.Timestamp):
                new_col = column.isoformat()
            else:
                new_col = str(column).strip().replace(" ", "_").lower()
            df.rename(columns={column: new_col}, inplace=True)
        
        return df.to_dict(orient="records")

    def _convert_list(self, values: list) -> list:
        """Convert list values to JSON serializable format.
        
        Args:
            values (list): List of values to convert
            
        Returns:
            list: Converted list with JSON serializable values
        """
        data = []
        for v in values:
            if isinstance(v, pd.Timestamp):
                v = v.isoformat()
            elif hasattr(v, 'isoformat'):  # Handle other datetime-like objects
                v = v.isoformat()
            elif hasattr(v, 'strftime'):  # Handle date objects
                v = v.strftime('%Y-%m-%d')
            elif pd.isna(v):
                v = None
            data.append(v)
        return data

    def _convert_to_json(self, data_json: Dict | List) -> Dict | List:
        """Convert data to JSON serializable format handling timestamps.
        
        Args:
            data_json (Dict | List): Data to convert
            
        Returns:
            Dict | List: JSON serializable data
        """
        if isinstance(data_json, dict):
            data_json = [data_json]
            
        for record in data_json:
            if isinstance(record, dict):
                for key, value in record.items():
                    if pd.isna(value):  # Handle NaN values
                        record[key] = None
                    elif isinstance(value, pd.Timestamp):  # Convert timestamps to ISO format
                        record[key] = value.isoformat()
                    elif isinstance(value, list):  # Handle lists recursively
                        record[key] = self._convert_list(value)
                    elif hasattr(value, 'isoformat'):  # Handle other datetime-like objects
                        record[key] = value.isoformat()
                    elif hasattr(value, 'strftime'):  # Handle date objects
                        record[key] = value.strftime('%Y-%m-%d')
        return data_json

    def _save_data(self, data: Any, prefix: str, filename: str) -> Any:
        """Save data to storage and return it.
        
        Args:
            data (Any): Data to save
            prefix (str): Storage prefix path
            filename (str): File name
            
        Returns:
            Any: The saved data
        """
        try:
            output_dir = os.path.join(self.__configuration.data_store_path, prefix)
            save_json(data, output_dir, filename)
            return data
        except Exception as e:
            logger.error(f"Error saving data to {prefix}/{filename}: {e}")
            return data

    @cache(lambda self, symbol: f"ticker_info_{symbol}", cache_type=DataType.JSON, ttl=datetime.timedelta(hours=1))
    def get_ticker_info(self, symbol: str) -> Dict:
        """Get basic information for a stock ticker.
        
        Args:
            symbol (str): Stock ticker symbol (e.g., "AAPL", "ALO.PA")
            
        Returns:
            Dict: Ticker information including company details, financial metrics
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            prefix = f"tickers/{symbol}"
            filename = f"{symbol}_info.json"
            return self._save_data(info, prefix, filename)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get ticker info for {symbol}: {str(e)}")

    @cache(lambda self, symbol, period: f"ticker_history_{symbol}_{period}", cache_type=DataType.JSON, ttl=datetime.timedelta(minutes=15))
    def get_ticker_history(self, symbol: str, period: str = "1mo") -> List[Dict]:
        """Get historical price data for a stock ticker.
        
        Args:
            symbol (str): Stock ticker symbol
            period (str): Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            
        Returns:
            List[Dict]: Historical price data with OHLCV information
        """
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period=period)
            history_data = self._result_df_to_dict(history)
            prefix = f"tickers/{symbol}"
            filename = f"{symbol}_history_{period}.json"
            return self._save_data(history_data, prefix, filename)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get ticker history for {symbol}: {str(e)}")

    @cache(lambda self, symbol: f"ticker_financials_{symbol}", cache_type=DataType.JSON, ttl=datetime.timedelta(hours=6))
    def get_ticker_financials(self, symbol: str) -> Dict:
        """Get financial statements for a stock ticker.
        
        Args:
            symbol (str): Stock ticker symbol
            
        Returns:
            Dict: Financial data including income statement, balance sheet, cash flow
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Get quarterly income statement
            quarterly_income_stmt = self._result_df_to_dict(ticker.quarterly_income_stmt)
            
            # Get calendar and analyst price targets
            calendar = self._convert_to_json(ticker.calendar) if hasattr(ticker, 'calendar') and ticker.calendar is not None else []
            analyst_price_targets = ticker.analyst_price_targets if hasattr(ticker, 'analyst_price_targets') else {}
            
            financials = {
                "quarterly_income_stmt": quarterly_income_stmt,
                "calendar": calendar,
                "analyst_price_targets": analyst_price_targets
            }
            
            prefix = f"tickers/{symbol}"
            filename = f"{symbol}_financials.json"
            return self._save_data(financials, prefix, filename)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get ticker financials for {symbol}: {str(e)}")

    @cache(lambda self, sector_key: f"sector_info_{sector_key}", cache_type=DataType.JSON, ttl=datetime.timedelta(hours=2))
    def get_sector_info(self, sector_key: str) -> Dict:
        """Get detailed information about a market sector.
        
        Args:
            sector_key (str): Sector identifier (e.g., "technology", "healthcare", "financials")
            
        Returns:
            Dict: Sector information including top companies, ETFs, mutual funds, industries
        """
        try:
            sector = yf.Sector(sector_key)
            
            sector_info = {
                "key": sector.key,
                "name": sector.name,
                "symbol": sector.symbol,
                "ticker": sector.ticker.info if hasattr(sector.ticker, 'info') else {},
                "overview": sector.overview if hasattr(sector, 'overview') else {},
                "top_companies": self._result_df_to_dict(sector.top_companies) if hasattr(sector, 'top_companies') else [],
                "research_reports": sector.research_reports if hasattr(sector, 'research_reports') else [],
                "top_etfs": sector.top_etfs if hasattr(sector, 'top_etfs') else [],
                "top_mutual_funds": sector.top_mutual_funds if hasattr(sector, 'top_mutual_funds') else [],
                "industries": self._result_df_to_dict(sector.industries) if hasattr(sector, 'industries') else []
            }
            
            prefix = f"sectors/{sector_key}"
            filename = f"{sector_key}_info.json"
            return self._save_data(sector_info, prefix, filename)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get sector info for {sector_key}: {str(e)}")

    @cache(lambda self, industry_key: f"industry_info_{industry_key}", cache_type=DataType.JSON, ttl=datetime.timedelta(hours=2))
    def get_industry_info(self, industry_key: str) -> Dict:
        """Get detailed information about a market industry.
        
        Args:
            industry_key (str): Industry identifier (e.g., "software", "biotech", "banks")
            
        Returns:
            Dict: Industry information including sector details and top companies
        """
        try:
            industry = yf.Industry(industry_key)
            
            industry_info = {
                "sector_key": industry.sector_key if hasattr(industry, 'sector_key') else "",
                "sector_name": industry.sector_name if hasattr(industry, 'sector_name') else "",
                "top_performing_companies": self._result_df_to_dict(industry.top_performing_companies) if hasattr(industry, 'top_performing_companies') else [],
                "top_growth_companies": self._result_df_to_dict(industry.top_growth_companies) if hasattr(industry, 'top_growth_companies') else []
            }
            
            prefix = f"industries/{industry_key}"
            filename = f"{industry_key}_info.json"
            return self._save_data(industry_info, prefix, filename)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get industry info for {industry_key}: {str(e)}")

    @cache(lambda self, company_name: f"search_{company_name.replace(' ', '_')}", cache_type=DataType.JSON, ttl=datetime.timedelta(hours=1))
    def search_ticker(self, company_name: str) -> List[Dict]:
        """Search for ticker symbols by company name.
        
        Args:
            company_name (str): Name of the company to search for
            
        Returns:
            List[Dict]: Search results with symbol, name, exchange information
        """
        try:
            results = search(company_name)
            quotes = results.get("quotes", []) if isinstance(results, dict) else []
            
            prefix = f"search/{company_name.replace(' ', '_')}"
            filename = f"{company_name.replace(' ', '_')}_search.json"
            return self._save_data(quotes, prefix, filename)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to search for {company_name}: {str(e)}")

def as_tools(configuration: YfinanceIntegrationConfiguration):
    """Convert YfinanceIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = YfinanceIntegration(configuration)

    class TickerSymbolSchema(BaseModel):
        symbol: str = Field(..., description="Stock ticker symbol (e.g., 'AAPL', 'ALO.PA', 'TSLA')")

    class TickerHistorySchema(BaseModel):
        symbol: str = Field(..., description="Stock ticker symbol")
        period: str = Field("1mo", description="Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max")

    class SectorKeySchema(BaseModel):
        sector_key: str = Field(..., description="Sector identifier (e.g., 'technology', 'healthcare', 'financials', 'industrials')")

    class IndustryKeySchema(BaseModel):
        industry_key: str = Field(..., description="Industry identifier (e.g., 'software', 'biotech', 'banks', 'railroads')")

    class CompanySearchSchema(BaseModel):
        company_name: str = Field(..., description="Company name to search for ticker symbol")

    return [
        StructuredTool(
            name="yfinance_get_ticker_info",
            description="Get basic information for a stock ticker including company details and financial metrics",
            func=integration.get_ticker_info,
            args_schema=TickerSymbolSchema
        ),
        StructuredTool(
            name="yfinance_get_ticker_history",
            description="Get historical price data for a stock ticker with OHLCV information",
            func=integration.get_ticker_history,
            args_schema=TickerHistorySchema
        ),
        StructuredTool(
            name="yfinance_get_ticker_financials",
            description="Get financial statements for a stock ticker including income statement, calendar, and analyst targets",
            func=integration.get_ticker_financials,
            args_schema=TickerSymbolSchema
        ),
        StructuredTool(
            name="yfinance_get_sector_info",
            description="Get detailed information about a market sector including top companies, ETFs, and industries",
            func=integration.get_sector_info,
            args_schema=SectorKeySchema
        ),
        StructuredTool(
            name="yfinance_get_industry_info",
            description="Get detailed information about a market industry including top performing and growth companies",
            func=integration.get_industry_info,
            args_schema=IndustryKeySchema
        ),
        StructuredTool(
            name="yfinance_search_ticker",
            description="Search for ticker symbols by company name to find the correct stock symbol",
            func=integration.search_ticker,
            args_schema=CompanySearchSchema
        )
    ]
