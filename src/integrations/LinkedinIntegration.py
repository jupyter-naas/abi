from typing import Dict, List, Optional
import requests
import time
from datetime import datetime
from dataclasses import dataclass
from pydantic import BaseModel, Field

from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration

@dataclass
class LinkedinIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn integration.
    
    Attributes:
        li_at (str): LinkedIn li_at cookie value for authentication
        jsessionid (str): LinkedIn JSESSIONID cookie value for authentication
        base_url (str): Base URL for LinkedIn API
        custom_api_url (str): Custom API URL for enhanced LinkedIn operations
    """
    li_at: str
    jsessionid: str
    base_url: str = "https://www.linkedin.com/voyager/api"
    custom_api_url: str = "https://3hz1hdpnlf.execute-api.eu-west-1.amazonaws.com/prod"

class LinkedinIntegration(Integration):
    """LinkedIn API integration client."""

    __configuration: LinkedinIntegrationConfiguration

    def __init__(self, configuration: LinkedinIntegrationConfiguration):
        """Initialize LinkedIn client with authentication cookies."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        # Initialize cookies and headers
        self.cookies = {
            "li_at": self.__configuration.li_at,
            "JSESSIONID": f'"{self.__configuration.jsessionid}"'
        }
        
        self.headers = {
            "X-Li-Lang": "en_US",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "Cache-Control": "no-cache", 
            "csrf-Token": self.__configuration.jsessionid,
            "X-Requested-With": "XMLHttpRequest",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        self.custom_headers = {
            "Content-Type": "application/json"
        }

        # # Test connection
        # try:
        #     self._make_request("GET", "/identity/profiles/me")
        # except Exception as e:
        #     raise IntegrationConnectionError(f"Failed to connect to LinkedIn: {str(e)}")

    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None, use_custom_api: bool = False) -> Dict:
        """Make HTTP request to LinkedIn API."""
        base = self.__configuration.custom_api_url if use_custom_api else self.__configuration.base_url
        url = f"{base}{endpoint}"
        headers = self.custom_headers if use_custom_api else self.headers
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                cookies=self.cookies if not use_custom_api else None,
                params=params,
                json=self.cookies if use_custom_api else data
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"LinkedIn API request failed: {str(e)}")

    def get_profile(self, profile_url: str) -> Dict:
        """Get a LinkedIn profile by URL."""
        profile_id = self._get_profile_id(profile_url)
        return self._make_request("GET", f"/identity/profiles/{profile_id}")

    def get_profile_info(self, profile_url: str) -> Dict:
        """Get detailed profile information using custom API."""
        profile_id = self._get_profile_id(profile_url)
        return self._make_request("POST", f"/profile/getTopCard?profile_id={profile_id}", use_custom_api=True)

    def get_company(self, company_url: str) -> Dict:
        """Get a LinkedIn company by URL."""
        return self._make_request("POST", f"/company/getInfo?company_url={company_url}", use_custom_api=True)

    def get_company_followers(self, company_url: str, start: int = 0, count: int = 100) -> Dict:
        """Get company followers using custom API."""
        return self._make_request(
            "POST", 
            f"/company/getFollowers?company_url={company_url}&start={start}&count={count}", 
            use_custom_api=True
        )

    def get_post_stats(self, post_url: str) -> Dict:
        """Get post statistics using custom API."""
        activity_id = self._get_activity_id(post_url)
        return self._make_request("POST", f"/post/getStats?activity_id={activity_id}", use_custom_api=True)

    def get_post_comments(self, post_url: str, start: int = 0, count: int = 100) -> Dict:
        """Get post comments using custom API."""
        activity_id = self._get_activity_id(post_url)
        return self._make_request(
            "POST", 
            f"/post/getComments?activity_id={activity_id}&start={start}&count={count}", 
            use_custom_api=True
        )

    @staticmethod
    def _get_profile_id(url: str) -> str:
        """Extract profile ID from LinkedIn profile URL."""
        return url.rsplit("/in/")[-1].rsplit("/")[0]

    @staticmethod
    def _get_company_id(url: str) -> str:
        """Extract company ID from LinkedIn company URL."""
        return url.rsplit("/company/")[-1].rsplit("/")[0]

    @staticmethod
    def _get_activity_id(url: str) -> str:
        """Extract activity ID from LinkedIn post URL."""
        if "-activity-" in url:
            return url.split("-activity-")[-1].split("-")[0]
        if ":activity:" in url:
            return url.split(":activity:")[-1].split("/")[0]
        return None

def as_tools(configuration: LinkedinIntegrationConfiguration):
    """Convert LinkedIn integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    
    integration = LinkedinIntegration(configuration)

    class GetProfileSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")

    class GetCompanySchema(BaseModel):
        company_url: str = Field(..., description="LinkedIn company URL")

    class GetCompanyFollowersSchema(BaseModel):
        company_url: str = Field(..., description="LinkedIn company URL")
        start: int = Field(0, description="Starting index for pagination")
        count: int = Field(100, description="Number of followers to retrieve")

    class GetPostStatsSchema(BaseModel):
        post_url: str = Field(..., description="LinkedIn post URL")

    class GetPostCommentsSchema(BaseModel):
        post_url: str = Field(..., description="LinkedIn post URL")
        start: int = Field(0, description="Starting index for pagination")
        count: int = Field(100, description="Number of comments to retrieve")
    
    return [
        StructuredTool(
            name="get_linkedin_profile",
            description="Get basic details about a LinkedIn profile",
            func=lambda profile_url: integration.get_profile(profile_url),
            args_schema=GetProfileSchema
        ),
        StructuredTool(
            name="get_linkedin_profile_info",
            description="Get detailed information about a LinkedIn profile",
            func=lambda profile_url: integration.get_profile_info(profile_url),
            args_schema=GetProfileSchema
        ),
        StructuredTool(
            name="get_linkedin_company",
            description="Get details about a LinkedIn company",
            func=lambda company_url: integration.get_company(company_url),
            args_schema=GetCompanySchema
        ),
        StructuredTool(
            name="get_linkedin_company_followers",
            description="Get followers of a LinkedIn company",
            func=lambda company_url, start=0, count=100: integration.get_company_followers(company_url, start, count),
            args_schema=GetCompanyFollowersSchema
        ),
        StructuredTool(
            name="get_linkedin_post_stats",
            description="Get statistics about a LinkedIn post",
            func=lambda post_url: integration.get_post_stats(post_url),
            args_schema=GetPostStatsSchema
        ),
        StructuredTool(
            name="get_linkedin_post_comments",
            description="Get comments on a LinkedIn post",
            func=lambda post_url, start=0, count=100: integration.get_post_comments(post_url, start, count),
            args_schema=GetPostCommentsSchema
        )
    ]
