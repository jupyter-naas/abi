from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
import requests
from typing import Dict, Optional
from abi import logger

LOGO_URL = (
    "https://media.glassdoor.com/sqll/100431/glassdoor-squareLogo-1689738456066.png"
)


@dataclass
class GlassdoorIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Glassdoor integration.

    Attributes:
        partner_id (str): Glassdoor Partner ID for authentication
        api_key (str): Glassdoor API key for authentication
        base_url (str): Base URL for Glassdoor API
    """

    partner_id: str
    api_key: str
    base_url: str = "https://api.glassdoor.com/api/api.htm"


class GlassdoorIntegration(Integration):
    """Glassdoor integration class for interacting with Glassdoor API.

    This class provides methods to interact with Glassdoor's API endpoints.
    It handles authentication and request management.

    Attributes:
        __configuration (GlassdoorIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: GlassdoorIntegrationConfiguration

    def __init__(self, configuration: GlassdoorIntegrationConfiguration):
        """Initialize Glassdoor client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

    def _make_request(self, action: str, params: Dict = None) -> Dict:
        """Make HTTP request to Glassdoor API.

        Args:
            action (str): API action to perform
            params (Dict, optional): Additional parameters for the request

        Returns:
            Dict: JSON response from the API

        Raises:
            IntegrationConnectionError: If the API request fails
        """
        try:
            # Base parameters required for all requests
            base_params = {
                "v": "1",
                "format": "json",
                "t.p": self.__configuration.partner_id,
                "t.k": self.__configuration.api_key,
                "action": action,
                "userip": "0.0.0.0",
                "useragent": "Mozilla/5.0",
            }

            # Merge base parameters with additional parameters
            if params:
                base_params.update(params)

            response = requests.get(self.__configuration.base_url, params=base_params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Glassdoor API request failed: {str(e)}")
            raise IntegrationConnectionError(f"Glassdoor API request failed: {str(e)}")

    def search_companies(self, query: str, location: Optional[str] = None) -> Dict:
        """Search for companies on Glassdoor.

        Args:
            query (str): Company name or search term
            location (str, optional): Location to filter results

        Returns:
            Dict: Company search results
        """
        params = {"q": query}
        if location:
            params["l"] = location
        return self._make_request("employers", params)

    def get_company_reviews(self, company_id: str, page: int = 1) -> Dict:
        """Get reviews for a specific company.

        Args:
            company_id (str): Glassdoor company ID
            page (int, optional): Page number for pagination. Defaults to 1.

        Returns:
            Dict: Company reviews data
        """
        params = {"employerId": company_id, "page": page}
        return self._make_request("reviews", params)

    def get_company_salaries(self, company_id: str) -> Dict:
        """Get salary information for a specific company.

        Args:
            company_id (str): Glassdoor company ID

        Returns:
            Dict: Company salary data
        """
        params = {"employerId": company_id}
        return self._make_request("salaries", params)

    def get_company_interviews(self, company_id: str, page: int = 1) -> Dict:
        """Get interview reviews for a specific company.

        Args:
            company_id (str): Glassdoor company ID
            page (int, optional): Page number for pagination. Defaults to 1.

        Returns:
            Dict: Company interview data
        """
        params = {"employerId": company_id, "page": page}
        return self._make_request("interviews", params)

    def get_company_benefits(self, company_id: str) -> Dict:
        """Get benefits information for a specific company.

        Args:
            company_id (str): Glassdoor company ID

        Returns:
            Dict: Company benefits data
        """
        params = {"employerId": company_id}
        return self._make_request("benefits", params)

    def get_job_listings(
        self, keyword: str, location: Optional[str] = None, page: int = 1
    ) -> Dict:
        """Search for job listings on Glassdoor.

        Args:
            keyword (str): Job title or search term
            location (str, optional): Location to filter results
            page (int, optional): Page number for pagination. Defaults to 1.

        Returns:
            Dict: Job listings data
        """
        params = {"keyword": keyword, "page": page}
        if location:
            params["location"] = location
        return self._make_request("jobs", params)


def as_tools(configuration: GlassdoorIntegrationConfiguration):
    """Convert Glassdoor integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GlassdoorIntegration(configuration)

    class SearchCompaniesSchema(BaseModel):
        query: str = Field(..., description="Company name or search term")
        location: Optional[str] = Field(None, description="Location to filter results")

    class GetCompanyReviewsSchema(BaseModel):
        company_id: str = Field(..., description="Glassdoor company ID")
        page: int = Field(default=1, description="Page number for pagination")

    class GetCompanySalariesSchema(BaseModel):
        company_id: str = Field(..., description="Glassdoor company ID")

    class GetCompanyInterviewsSchema(BaseModel):
        company_id: str = Field(..., description="Glassdoor company ID")
        page: int = Field(default=1, description="Page number for pagination")

    class GetCompanyBenefitsSchema(BaseModel):
        company_id: str = Field(..., description="Glassdoor company ID")

    class GetJobListingsSchema(BaseModel):
        keyword: str = Field(..., description="Job title or search term")
        location: Optional[str] = Field(None, description="Location to filter results")
        page: int = Field(default=1, description="Page number for pagination")

    return [
        StructuredTool(
            name="glassdoor_search_companies",
            description="Search for companies on Glassdoor",
            func=lambda query, location: integration.search_companies(query, location),
            args_schema=SearchCompaniesSchema,
        ),
        StructuredTool(
            name="glassdoor_get_company_reviews",
            description="Get reviews for a specific company",
            func=lambda company_id, page: integration.get_company_reviews(
                company_id, page
            ),
            args_schema=GetCompanyReviewsSchema,
        ),
        StructuredTool(
            name="glassdoor_get_company_salaries",
            description="Get salary information for a specific company",
            func=lambda company_id: integration.get_company_salaries(company_id),
            args_schema=GetCompanySalariesSchema,
        ),
        StructuredTool(
            name="glassdoor_get_company_interviews",
            description="Get interview reviews for a specific company",
            func=lambda company_id, page: integration.get_company_interviews(
                company_id, page
            ),
            args_schema=GetCompanyInterviewsSchema,
        ),
        StructuredTool(
            name="glassdoor_get_company_benefits",
            description="Get benefits information for a specific company",
            func=lambda company_id: integration.get_company_benefits(company_id),
            args_schema=GetCompanyBenefitsSchema,
        ),
        StructuredTool(
            name="glassdoor_get_job_listings",
            description="Search for job listings on Glassdoor",
            func=lambda keyword, location, page: integration.get_job_listings(
                keyword, location, page
            ),
            args_schema=GetJobListingsSchema,
        ),
    ]
