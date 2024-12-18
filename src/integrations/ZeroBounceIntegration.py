from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict, Optional

@dataclass
class ZeroBounceIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for ZeroBounce integration.
    
    Attributes:
        api_key (str): ZeroBounce API key for authentication
        base_url (str): Base URL for ZeroBounce API
    """
    api_key: str
    base_url: str = "https://api.zerobounce.net/v2"

class ZeroBounceIntegration(Integration):
    """ZeroBounce integration for email validation.
    
    This class provides methods to interact with ZeroBounce's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (ZeroBounceIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: ZeroBounceIntegrationConfiguration

    def __init__(self, configuration: ZeroBounceIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def validate_email(self, email: str, ip_address: Optional[str] = None) -> Dict:
        """Validate an email address using ZeroBounce API.
        
        Args:
            email (str): The email address to validate
            ip_address (str, optional): IP address to include in the validation
        
        Returns:
            Dict: The validation result containing status and other details
        """
        params = {
            "api_key": self.__configuration.api_key,
            "email": email,
        }
        if ip_address:
            params["ip_address"] = ip_address

        response = requests.get(
            f"{self.__configuration.base_url}/validate",
            params=params
        )
        response.raise_for_status()
        return response.json()

    def get_credits(self) -> int:
        """Get the number of remaining API credits.
        
        Returns:
            int: Number of remaining credits
        """
        params = {
            "api_key": self.__configuration.api_key
        }
        response = requests.get(
            f"{self.__configuration.base_url}/getcredits",
            params=params
        )
        response.raise_for_status()
        return response.json()["Credits"]

    def get_api_usage(self, start_date: str, end_date: str) -> Dict:
        """Get API usage statistics for a date range.
        
        Args:
            start_date (str): Start date in format 'YYYY-MM-DD'
            end_date (str): End date in format 'YYYY-MM-DD'
            
        Returns:
            Dict: Usage statistics for the specified period
        """
        params = {
            "api_key": self.__configuration.api_key,
            "start_date": start_date,
            "end_date": end_date
        }
        response = requests.get(
            f"{self.__configuration.base_url}/getapiusage",
            params=params
        )
        response.raise_for_status()
        return response.json() 
    

def as_tools(configuration: ZeroBounceIntegrationConfiguration):
    """Convert ZeroBounce integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = ZeroBounceIntegration(configuration)

    class ValidateEmailSchema(BaseModel):
        email: str = Field(..., description="Email address to validate")
        ip_address: Optional[str] = Field(None, description="IP address to include in the validation") 

    class GetCreditsSchema(BaseModel):
        pass

    class GetApiUsageSchema(BaseModel):
        start_date: str = Field(..., description="Start date in format 'YYYY-MM-DD'")
        end_date: str = Field(..., description="End date in format 'YYYY-MM-DD'")

    return [
        StructuredTool(
            name="validate_email",
            description="Validate an email address using ZeroBounce API",
            func=integration.validate_email,
            args_schema=ValidateEmailSchema
        ),
        StructuredTool(
            name="get_credits",
            description="Get the number of remaining API credits",
            func=integration.get_credits,
            args_schema=GetCreditsSchema
        ),
        StructuredTool(
            name="get_api_usage",
            description="Get API usage statistics for a date range",
            func=integration.get_api_usage,
            args_schema=GetApiUsageSchema
        )
    ]