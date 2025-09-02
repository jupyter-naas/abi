from typing import Dict
import requests
import urllib.parse
from dataclasses import dataclass
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
import os
from src.utils.Storage import get_json, save_json, save_image
import pydash
from abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
import datetime
from abi import logger

cache = CacheFactory.CacheFS_find_storage(subpath="linkedin")

@dataclass
class LinkedInIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn integration.
    
    Attributes:
        li_at (str): LinkedIn li_at cookie value for authentication
        JSESSIONID (str): LinkedIn JSESSIONID cookie value for authentication
        base_url (str): Base URL for LinkedIn API
        data_store_path (str): Path to store cached data
        use_cache (bool): Whether to use cache
    """
    li_at: str
    JSESSIONID: str
    base_url: str = "https://www.linkedin.com/voyager/api"
    data_store_path: str = "datastore/linkedin"
    use_cache: bool = True

class LinkedInIntegration(Integration):
    """LinkedIn API integration client focused on organization information."""

    __configuration: LinkedInIntegrationConfiguration

    def __init__(self, configuration: LinkedInIntegrationConfiguration):
        """Initialize LinkedIn client with authentication cookies."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__configuration.JSESSIONID = self.__configuration.JSESSIONID.replace('"', '')
        
        # Initialize cookies and headers
        self.cookies = {
            "li_at": self.__configuration.li_at,
            "JSESSIONID": self.__configuration.JSESSIONID
        }
        
        self.headers = {
            "X-Li-Lang": "en_US",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "Cache-Control": "no-cache", 
            "csrf-Token": self.__configuration.JSESSIONID,
            "X-Requested-With": "XMLHttpRequest",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    def __save_images(self, data: dict, key: str, output_dir: str):
        """
        Extracts picture URLs from a nested dictionary.

        Args:
            data (dict): The dictionary containing picture data.
            key (str): The key to extract picture URLs from.
            output_dir (str): The directory to save the images to.

        Returns:
            list: A list of picture URLs.
        """
        entity_urn = data.get("entityUrn")
        if key == "logo":
            root_url = pydash.get(data, f"{key}.image.rootUrl")
            artifacts = pydash.get(data, f"{key}.image.artifacts", [])
        else:
            root_url = pydash.get(data, f"{key}.rootUrl")
            artifacts = pydash.get(data, f"{key}.artifacts", [])
        if root_url:
            for x in artifacts:
                file_url = x.get("fileIdentifyingUrlPathSegment")
                image_url = f"{root_url}{file_url}"
                response = requests.get(image_url)
                save_image(response.content, output_dir, f"{entity_urn}_{key}_{file_url.split('/')[0]}.png")

    def __save_json(self, prefix: str, filename: str, data: dict, save_image=False) -> Dict:
        """Save data to cache."""
        save_json(data, os.path.join(self.__configuration.data_store_path, prefix), filename + ".json")
        
        # Initialize output directory
        output_dir = os.path.join(self.__configuration.data_store_path, prefix)

        # Save dict data
        output_dir_data = os.path.join(output_dir, "data")
        data_dict = data.get("data", {})
        if len(get_json(output_dir_data, f"{filename}_data.json")) == 0:
            save_json(data_dict, output_dir_data, f"{filename}_data.json")

        # Save dict included
        output_dir_included = os.path.join(output_dir, "included")
        included = data.get("included", [])
        if len(get_json(output_dir_included, f"{filename}_included.json")) == 0:
            save_json(included, output_dir_included, f"{filename}_included.json")
        for include in included:
            dict_type = include.get("$type")
            dict_label = dict_type.split(".")[-1].strip()
            output_dir_dict_type = os.path.join(output_dir_included, dict_label)
            entity_urn = include.get("entityUrn")
            if len(get_json(output_dir_dict_type, f"{entity_urn}.json")) == 0:
                save_json(include, output_dir_dict_type, f"{entity_urn}.json")
            if save_image:
                for key in ["logo", "backgroundImage", "profile"]:
                    if include.get(key):
                        self.__save_images(include, key, output_dir_dict_type)
                    else:
                        save_json({}, output_dir_dict_type, f"{entity_urn}.json")
        return data

    @cache(lambda self, prefix, filename, method, endpoint, params: method + "_" + endpoint + ("_".join(f"{k}_{v}" for k,v in params.items()) if params else ""), cache_type=DataType.JSON, ttl=datetime.timedelta(days=7))
    def _make_request(
        self,
        prefix: str,
        filename: str,
        method: str, 
        endpoint: str, 
        params: Dict | None = None,
    ) -> Dict:
        """Make HTTP request to LinkedIn API."""        
        # Make request
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            logger.info(f"Making request to {url} with method {method} and params {params}")
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                cookies=self.cookies,
                params=params
            )
            response.raise_for_status()
            return self.__save_json(prefix=prefix, filename=filename, data=response.json()) if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"LinkedIn API request failed: {str(e)}")

    def get_organization_id(self, url: str) -> str:
        """Extract organization ID from LinkedIn URL.
        
        Handles company, school and showcase pages.
        """
        if "/company/" in url:
            return url.rsplit("/company/")[-1].rsplit("/")[0]
        elif "/school/" in url:
            return url.rsplit("/school/")[-1].rsplit("/")[0] 
        elif "/showcase/" in url:
            return url.rsplit("/showcase/")[-1].rsplit("/")[0]
        else:
            raise ValueError(f"Invalid LinkedIn URL: {url}")
    
    def get_organization_info(self, linkedin_url: str) -> Dict:
        """Get detailed information about a LinkedIn organization using LinkedIn's native API.
        
        Args:
            linkedin_url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/company/naas-ai/")
            
        Returns:
            Dict: Raw organization data from LinkedIn API
        """
        # Get organization ID
        org_id = self.get_organization_id(linkedin_url)
        prefix = os.path.join("get_organization_info", org_id)
        
        # Set up parameters for the request
        params = {
            "decorationId": "com.linkedin.voyager.deco.organization.web.WebFullCompanyMain-33",
            "q": "universalName",
            "universalName": org_id,
        }
        
        endpoint = f"/organization/companies?{urllib.parse.urlencode(params)}"
        data = self._make_request(prefix=prefix, filename=org_id, method="GET", endpoint=endpoint)
        return data
    
    def get_profile_id(self, linkedin_url: str) -> str:
        """Extract profile ID from LinkedIn URL.
        
        Handles profile URLs with or without the /in/ prefix.
        """
        if "/in/" in linkedin_url:  
            return linkedin_url.rsplit("/in/")[-1].rsplit("/")[0]
        return ""
    
    def get_profile_view(self, linkedin_url: str) -> Dict:
        """Get profile view for a LinkedIn organization.
        
        Args:
            linkedin_url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")
            
        Returns:
            Dict: Raw profile view data from LinkedIn API
        """
        # Get organization ID
        profile_id = self.get_profile_id(linkedin_url)
        prefix = os.path.join("get_profile_view", profile_id)
        
        endpoint = f"/identity/profiles/{profile_id}/profileView"
        data = self._make_request(prefix=prefix, filename=profile_id, method="GET", endpoint=endpoint)
        return data

    def get_profile_top_card(self, linkedin_url: str) -> Dict:
        """Get profile top card information for a LinkedIn profile.
        
        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")
            
        Returns:
            Dict: Raw profile top card data from LinkedIn API
        """
        # Get profile ID
        profile_id = self.get_profile_id(linkedin_url)
        prefix = os.path.join("get_profile_top_card", profile_id)
        
        endpoint = f"/graphql?variables=(vanityName:{profile_id})&queryId=voyagerIdentityDashProfiles.0bc93b66ba223b9d30d1cb5c05ff031a"
        data = self._make_request(prefix=prefix, filename=profile_id, method="GET", endpoint=endpoint)
        return data
    
    def get_activity_id(self, linkedin_url: str) -> str:
        """Extract activity ID from LinkedIn URL.
        
        Handles activity URLs with or without the -activity- or :activity: prefix.
        """
        if "-activity-" in linkedin_url:
            return linkedin_url.split("-activity-")[-1].split("-")[0]
        elif ":activity:" in linkedin_url:
            return linkedin_url.split(":activity:")[-1].split("/")[0]
        return ""
    
    def get_post_stats(self, linkedin_url: str) -> Dict:
        """Get activity for a LinkedIn activity.
        
        Args:
            linkedin_url (str): LinkedIn activity URL. It must contain -activity- in the URL.

        Returns:
            Dict: Raw post stats data from LinkedIn API
        """
        # Get activity ID
        activity_id = self.get_activity_id(linkedin_url)
        prefix = os.path.join("get_post_stats", activity_id)
            
        endpoint = f"/feed/updates/urn:li:activity:{activity_id}"
        data = self._make_request(prefix=prefix, filename=activity_id, method="GET", endpoint=endpoint)
        return data
    
    def get_post_reactions(self, linkedin_url: str, start: int = 0, count: int = 100, limit: int = -1) -> Dict:
        """Get reactions for a LinkedIn post.
        
        Args:
            activity_id (str): LinkedIn activity ID.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of reactions to fetch per request. Defaults to 100.
            limit (int, optional): Maximum number of reactions to return. Defaults to -1 (no limit).
        """
        # Get activity ID
        activity_id = self.get_activity_id(linkedin_url)
        prefix = os.path.join("get_post_reactions", activity_id)
        filename = f"{activity_id}_{start}_{count}"

        params = {
            "q": "reactionType",
            "start": start,
            "count": count,
            "threadUrn": f"urn:li:activity:{activity_id}",
        }
        endpoint = f"/feed/reactions?{urllib.parse.urlencode(params, doseq=True)}"

        all_data = None
        while True:
            if limit != -1 and limit < count:
                count = limit
                
            params["start"] = start
            params["count"] = count
            filename = f"{activity_id}_{start}_{count}"
            
            data = self._make_request(prefix=prefix, filename=filename, method="GET", endpoint=endpoint)
            
            if not all_data:
                all_data = data
            else:
                all_data["included"].extend(data.get("included", []))
                all_data["data"]["*elements"].extend(data["data"]["*elements"])
            
            total = data.get("data", {}).get("paging", {}).get("total", 0)
            fetched = start + len(data.get("data", {}).get("*elements", []))
            
            if fetched >= total:
                break
                
            if limit != -1:
                limit -= count
                if limit <= 0:
                    break
                    
            start += count
            
        return all_data
    
    def get_post_comments(self, linkedin_url: str, start: int = 0, count: int = 100, limit: int = -1) -> Dict:
        """Get comments for a LinkedIn post.
        
        Args:
            activity_id (str): LinkedIn activity ID.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of comments to fetch per request. Defaults to 100.
            limit (int, optional): Maximum number of comments to return. Defaults to -1 (no limit).
        """
        # Get activity ID
        activity_id = self.get_activity_id(linkedin_url)
        prefix = os.path.join("get_post_comments", activity_id)
        filename = f"{activity_id}_{start}_{count}"

        # Request
        params = {
            "q": "comments",
            "start": start,
            "count": count,
            "updateId": f"activity:{activity_id}",
            "sortOrder": "RECENT",
        }
        endpoint = f"/feed/comments?{urllib.parse.urlencode(params, safe='(),')}"
        
        all_data = None
        while True:
            if limit != -1 and limit < count:
                count = limit
                
            params["start"] = start
            params["count"] = count
            filename = f"{activity_id}_{start}_{count}"
            
            data = self._make_request(prefix=prefix, filename=filename, method="GET", endpoint=endpoint)
            
            if not all_data:
                all_data = data
            else:
                all_data["included"].extend(data.get("included", []))
                all_data["data"]["*elements"].extend(data["data"]["*elements"])
            
            total = data.get("data", {}).get("paging", {}).get("total", 0)
            fetched = start + len(data.get("data", {}).get("*elements", []))
            
            if fetched >= total:
                break
                
            if limit != -1:
                limit -= count
                if limit <= 0:
                    break
                    
            start += count
            
        return all_data
    
def as_tools(configuration: LinkedInIntegrationConfiguration):
    """Convert LinkedIn integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = LinkedInIntegration(configuration)

    class GetOrganizationInfoSchema(BaseModel):
        linkedin_url: str = Field(
            ..., 
            description="LinkedIn organization URL", 
            pattern=r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"
        )

    class GetProfileSchema(BaseModel):
        linkedin_url: str = Field(
            ..., 
            description="LinkedIn profile URL", 
            pattern=r"https://.+\.linkedin\.[^/]+/in/[^?]+"
        )

    class GetActivitySchema(BaseModel):
        linkedin_url: str = Field(
            ..., 
            description="LinkedIn activity ID extracted from the URL", 
        )

    return [
        StructuredTool(
            name="linkedin_get_organization_info",
            description="Get organization information for a LinkedIn organization",
            func=lambda linkedin_url: integration.get_organization_info(linkedin_url),
            args_schema=GetOrganizationInfoSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_view",
            description="Get profile view for a LinkedIn organization",
            func=lambda linkedin_url: integration.get_profile_view(linkedin_url),
            args_schema=GetProfileSchema
        ),
        StructuredTool(
            name="linkedin_get_post_stats",
            description="Get post stats for a LinkedIn activity",
            func=lambda linkedin_url: integration.get_post_stats(linkedin_url),
            args_schema=GetActivitySchema
        ),
        StructuredTool(
            name="linkedin_get_post_comments",
            description="Get comments for a LinkedIn activity",
            func=lambda linkedin_url: integration.get_post_comments(linkedin_url),
            args_schema=GetActivitySchema
        ),
        StructuredTool(
            name="linkedin_get_post_reactions",
            description="Get reactions for a LinkedIn activity",
            func=lambda linkedin_url: integration.get_post_reactions(linkedin_url),
            args_schema=GetActivitySchema
        )
    ]