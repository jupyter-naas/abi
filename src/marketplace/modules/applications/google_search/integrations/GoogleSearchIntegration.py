from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from googlesearch import search # type: ignore
import re
from typing import Optional, List
from abi import logger


@dataclass
class GoogleSearchIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for GoogleSearch."""
    pass

class GoogleSearchIntegration(Integration):
    """GoogleSearch integration for performing Google searches.
    
    This class provides methods to search Google and get list of urls from search results.
    """

    __configuration: GoogleSearchIntegrationConfiguration
    
    def __init__(self, configuration: GoogleSearchIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_google(
        self, 
        query: str,
        num: int = 10,
        stop: int = 10,
        tld: str = "com",
        pause: int = 2,
    ) -> Optional[str]:
        """Search for and extract LinkedIn company URL from Google search results.
        
        Args:
            query (str): Search query to perform
            num (int): Number of results to return. Defaults to 10
            stop (int): Number of results to stop at. Defaults to 10
            
        Returns:
            Optional[str]: LinkedIn company URL if found, None otherwise
        """
        results = search(query, tld=tld, num=num, stop=stop, pause=pause)
        return results
    
    def search_url(
        self, 
        query: str,
        pattern: str | None = None,
    ) -> List[str]:
        """Search for and extract LinkedIn URL from Google search results.
        
        Args:
            query (str): Search query to perform
            pattern (str): Pattern to use to extract the LinkedIn URL
        """
        # Search in Google
        logger.info(f"🔍 Searching for {query} in Google")
        results = self.search_google(query)
        if results is None:
            return []
        urls = []
        for result in results:
            if pattern is None:
                urls.append(result)
                continue

            match = re.search(pattern, result)
            # Return value if match is found
            if match is not None:
                urls.append(match.group(0).replace(" ", ""))

        logger.info(f"✅ Found {len(urls)} URLs")
        logger.info(urls)
        return urls
        
    def search_linkedin_organization_url(
        self, 
        organization_name: str,
    ) -> Optional[str]:
        """Search for and extract LinkedIn company URL from Google search results.
        
        Args:
            organization_name (str): Name of the organization to search for
        """
        pattern = r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"
        query = organization_name.lower().replace(" ", "+")+"+site:www.linkedin.com"
        results = self.search_url(query, pattern)
        return results[0] if results else None
    
    def search_linkedin_profile_url(
        self, 
        profile_name: str,
    ) -> Optional[str]:
        """Search for and extract LinkedIn profile URL from Google search results.
        
        Args:
            profile_name (str): Name of the profile to search for
        """
        pattern = r"https://.+\.linkedin\.[^/]+/in/[^?]+"
        query = profile_name.lower().replace(" ", "+")+"+site:linkedin.com"
        results = self.search_url(query, pattern)
        return results[0] if results else None

def as_tools(configuration: GoogleSearchIntegrationConfiguration):
    """Convert SerpAPI integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = GoogleSearchIntegration(configuration)
    
    class SearchSchema(BaseModel):
        query: str = Field(..., description="Search query")

    class SearchURLSchema(BaseModel):
        query: str = Field(..., description="Search query")
        pattern: str = Field(..., description="Pattern to use to extract the URL")

    class SearchLinkedInOrganizationSchema(BaseModel):
        organization_name: str = Field(..., description="Name of the organization to search for")

    class SearchLinkedInProfileSchema(BaseModel):
        profile_name: str = Field(..., description="Name of the profile to search for")

    return [
        StructuredTool(
            name="googlesearch_search",
            description="Search using Google Search",
            func=lambda **kwargs: integration.search_google(**kwargs),
            args_schema=SearchSchema
        ),
        StructuredTool(
            name="googlesearch_search_url",
            description="Search for a URL using Google Search",
            func=lambda **kwargs: integration.search_url(**kwargs),
            args_schema=SearchURLSchema
        ),
        StructuredTool(
            name="googlesearch_linkedin_organization",
            description="Search for LinkedIn organization URL using Google Search",
            func=lambda **kwargs: integration.search_linkedin_organization_url(**kwargs),
            args_schema=SearchLinkedInOrganizationSchema
        ),
        StructuredTool(
            name="googlesearch_linkedin_profile",
            description="Search for LinkedIn profile URL using Google Search",
            func=lambda **kwargs: integration.search_linkedin_profile_url(**kwargs),
            args_schema=SearchLinkedInProfileSchema
        ),
    ] 