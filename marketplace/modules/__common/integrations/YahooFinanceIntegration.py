from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional
import yfinance as yf
from datetime import datetime, timedelta

LOGO_URL = "https://logo.clearbit.com/yahoo.com"


@dataclass
class YahooFinanceIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Yahoo Finance integration.

    Attributes:
        user_agent (str): User agent string for API requests. Defaults to "YahooFinanceIntegration/1.0"
    """

    user_agent: str = "YahooFinanceIntegration/1.0"


class YahooFinanceIntegration(Integration):
    """Yahoo Finance API integration client.

    This integration provides methods to interact with Yahoo Finance
    to retrieve financial data and information.
    """

    __configuration: YahooFinanceIntegrationConfiguration

    def __init__(self, configuration: YahooFinanceIntegrationConfiguration):
        """Initialize Yahoo Finance client."""
        super().__init__(configuration)
        self.__configuration = configuration

    def get_stock_info(self, symbol: str) -> Dict:
        """Get basic information about a stock.

        Args:
            symbol (str): Stock symbol (e.g., 'AAPL')

        Returns:
            Dict: Stock information

        Raises:
            IntegrationConnectionError: If the stock info retrieval fails
        """
        try:
            ticker = yf.Ticker(symbol)
            return ticker.info
        except Exception as e:
            raise IntegrationConnectionError(f"Yahoo Finance request failed: {str(e)}")

    def get_historical_data(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Dict:
        """Get historical price data for a stock.

        Args:
            symbol (str): Stock symbol (e.g., 'AAPL')
            period (str, optional): Time period. Defaults to "1mo".
                Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
            interval (str, optional): Data interval. Defaults to "1d".
                Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo

        Returns:
            Dict: Historical price data

        Raises:
            IntegrationConnectionError: If the historical data retrieval fails
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            return df.to_dict(orient="index")
        except Exception as e:
            raise IntegrationConnectionError(f"Yahoo Finance request failed: {str(e)}")

    def get_financials(self, symbol: str) -> Dict:
        """Get financial statements for a stock.

        Args:
            symbol (str): Stock symbol (e.g., 'AAPL')

        Returns:
            Dict: Financial statements data

        Raises:
            IntegrationConnectionError: If the financials retrieval fails
        """
        try:
            ticker = yf.Ticker(symbol)
            return {
                "income_statement": ticker.income_stmt.to_dict(),
                "balance_sheet": ticker.balance_sheet.to_dict(),
                "cash_flow": ticker.cash_flow.to_dict(),
            }
        except Exception as e:
            raise IntegrationConnectionError(f"Yahoo Finance request failed: {str(e)}")

    def get_recommendations(self, symbol: str) -> List[Dict]:
        """Get analyst recommendations for a stock.

        Args:
            symbol (str): Stock symbol (e.g., 'AAPL')

        Returns:
            List[Dict]: List of recommendations

        Raises:
            IntegrationConnectionError: If the recommendations retrieval fails
        """
        try:
            ticker = yf.Ticker(symbol)
            recommendations = ticker.recommendations
            return (
                recommendations.to_dict(orient="records")
                if recommendations is not None
                else []
            )
        except Exception as e:
            raise IntegrationConnectionError(f"Yahoo Finance request failed: {str(e)}")


def as_tools(configuration: YahooFinanceIntegrationConfiguration):
    """Convert Yahoo Finance integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = YahooFinanceIntegration(configuration)

    class StockSymbolSchema(BaseModel):
        symbol: str = Field(..., description="Stock symbol (e.g., 'AAPL')")

    class HistoricalDataSchema(BaseModel):
        symbol: str = Field(..., description="Stock symbol (e.g., 'AAPL')")
        period: str = Field(
            default="1mo",
            description="Time period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)",
        )
        interval: str = Field(
            default="1d",
            description="Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)",
        )

    return [
        StructuredTool(
            name="yahoofinance_get_stock_info",
            description="Get basic information about a stock from Yahoo Finance.",
            func=lambda symbol: integration.get_stock_info(symbol),
            args_schema=StockSymbolSchema,
        ),
        StructuredTool(
            name="yahoofinance_get_historical_stock_data",
            description="Get historical price data for a stock from Yahoo Finance.",
            func=lambda symbol, period, interval: integration.get_historical_data(
                symbol, period, interval
            ),
            args_schema=HistoricalDataSchema,
        ),
        StructuredTool(
            name="yahoofinance_get_stock_financials",
            description="Get financial statements for a stock from Yahoo Finance.",
            func=lambda symbol: integration.get_financials(symbol),
            args_schema=StockSymbolSchema,
        ),
        StructuredTool(
            name="yahoofinance_get_stock_recommendations",
            description="Get analyst recommendations for a stock from Yahoo Finance.",
            func=lambda symbol: integration.get_recommendations(symbol),
            args_schema=StockSymbolSchema,
        ),
    ]
