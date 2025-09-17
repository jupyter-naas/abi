from abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from langchain_core.tools import StructuredTool, BaseTool
from pydantic import BaseModel, Field
from typing import Dict
from abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
import requests

cache = CacheFactory.CacheFS_find_storage(subpath="exchangeratesapi")

@dataclass
class ExchangeratesapiIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Exchangeratesapi integration.
    
    Attributes:
        api_key (str): Exchangeratesapi API key for authentication
    """
    api_key: str
    base_url: str = "https://api.exchangeratesapi.io/v1"

class ExchangeratesapiIntegration(Integration):
    """Exchangeratesapi integration class for interacting with Exchangeratesapi's API.
    
    This class provides methods to interact with Exchangeratesapi's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (ExchangeratesapiIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: ExchangeratesapiIntegrationConfiguration

    def __init__(self, configuration: ExchangeratesapiIntegrationConfiguration):
        """Initialize OpenAI client with configuration."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.params = {
            "access_key": self.__configuration.api_key
        }

    def _make_request(self, method: str, endpoint: str, params: Dict = {}) -> Dict:
        """Make HTTP request to Exchangeratesapi API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                params={**self.params, **(params or {})},
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Exchangeratesapi API request failed: {str(e)}")
    
    @cache(lambda self: "list_symbols", cache_type=DataType.JSON)
    def list_symbols(self) -> Dict:
        """List symbols."""
        return self._make_request("GET", "/symbols")
        
    @cache(lambda self, date, base, symbols: f"get_exchange_rates_{date}_{base}_{('ALL' if not symbols else ','.join(symbols))}", cache_type=DataType.JSON)
    def get_exchange_rates(self, date: str = "latest", base: str = "EUR", symbols: list[str] = []) -> Dict:
        """Get exchange rates.
        
        Args:
            date: The date to get the exchange rates for in format YYYY-MM-DD. Default is "latest".
            base: The base currency to get the exchange rates for. Default is "EUR".
            symbols: The symbols to get the exchange rates for. Default is all symbols.
        """
        params = {
            "base": base,
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._make_request("GET", f"/{date}", params)
    
def as_tools(configuration: ExchangeratesapiIntegrationConfiguration) -> list[BaseTool]:
    """Convert Exchangeratesapi integration into LangChain tools."""
    integration = ExchangeratesapiIntegration(configuration)

    class GetExchangeRatesSchema(BaseModel):
        date: str = Field(description="The date to get the exchange rates for in format YYYY-MM-DD. Default is 'latest'.")
        base: str = Field(description="The base currency to get the exchange rates for. Default is 'EUR'.")
        symbols: list[str] = Field(description="The symbols to get the exchange rates for. Default is all symbols.")

    class ListSymbolsSchema(BaseModel):
        pass

    return [
        StructuredTool(
            name="exchangeratesapi_get_exchange_rates",
            description="Get exchange rates for a given date, base and symbols.",
            func=lambda **kwargs: integration.get_exchange_rates(**kwargs),
            args_schema=GetExchangeRatesSchema
        ),
        StructuredTool(
            name="exchangeratesapi_list_symbols",
            description="List all currencies symbols and their names.",
            func=lambda **kwargs: integration.list_symbols(**kwargs),
            args_schema=ListSymbolsSchema
        ),
    ]