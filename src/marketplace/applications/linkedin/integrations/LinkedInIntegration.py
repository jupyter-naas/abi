from typing import Dict
import requests
import urllib.parse
from dataclasses import dataclass
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
import os
from src.utils.Storage import get_json, save_json, save_image
from abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
import datetime
from typing import Union, Any, List, MutableMapping
import json
import pydash as _

cache = CacheFactory.CacheFS_find_storage(subpath="linkedin")

@dataclass
class LinkedInIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn integration.
    
    Attributes:
        li_at (str): LinkedIn li_at cookie value for authentication
        JSESSIONID (str): LinkedIn JSESSIONID cookie value for authentication
        base_url (str): Base URL for LinkedIn API
        data_store_path (str): Path to store cached data
    """
    li_at: str
    JSESSIONID: str
    base_url: str = "https://www.linkedin.com/voyager/api"
    data_store_path: str = "datastore/linkedin"

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
            "x-li-lan": "en_US",
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "csrf-token": self.__configuration.JSESSIONID,
            "x-restli-protocol-version": "2.0.0"
        }

        
    def _flatten_dict(self, data: Union[Dict, Any], parent_key: str = '', sep: str = '_') -> Dict:
        """
        Flattens a nested dictionary.

        Args:
            data (dict): The dictionary to flatten.
            parent_key (str, optional): The base key for the flattened dictionary. Defaults to ''.
            sep (str, optional): The separator to use between keys. Defaults to '_'.

        Returns:
            dict: The flattened dictionary.
        """
        if isinstance(data, dict):
            items: list = []
            for k, v in data.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, MutableMapping):
                    items.extend(self._flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)
        return data

    def _clean_dict(self, data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
        """
        Recursively cleans a dictionary by removing keys that start with '*' or contain 'urn'.

        Args:
            data (dict or list): The dictionary or list to clean.

        Returns:
            dict or list: The cleaned dictionary or list.
        """
        if not isinstance(data, (dict, list)):
            return data
        if isinstance(data, list):
            return [val for val in (self._clean_dict(x) for x in data) if val is not None]
        return {
            k: val 
            for k, val in ((k, self._clean_dict(v)) for k, v in data.items()) 
            if val is not None and not k.startswith("*") and "urn" not in k.lower()
        }

    def _parse_clean(self, data: Dict, include_images: bool = True) -> Dict:
        """
        Parses and cleans LinkedIn profile data.

        Args:
            data (dict): The raw LinkedIn profile data.
            include_images (bool): Whether to process and include image URLs.

        Returns:
            dict: The parsed and cleaned data.
        """
        results: dict = {}
        included = _.get(data, "included", [])
        if len(included) == 0:
            return results
        
        for include in included:
            _type = include.get("$type")
            if _type is None or (_type.endswith("View") or _type.endswith("Group") or _type.endswith("Action")):
                continue
                
            if _type not in results:
                entities: list = []
                results[_type] = entities
            else:
                entities = results.get(_type, [])
                if entities is None:
                    entities = []
            
            # Add Image URL full if requested
            if include_images:
                for key in include:
                    if any(img in key.lower() for img in ["logo", "picture", "image"]):
                        picture_urls = self.__get_images(include, key)
                        if picture_urls:
                            include[key] = picture_urls[-1]  # Take the last (highest quality) URL
            
            # Pop useless values recursively
            def pop_keys(d):
                if isinstance(d, dict):
                    for key in ["trackingId", "$recipeTypes", "paging"]:
                        if key in d:
                            d.pop(key)
                    for v in d.values():
                        pop_keys(v)
                elif isinstance(d, list):
                    for item in d:
                        pop_keys(item)
            
            pop_keys(include)
            
            # Add new entities
            if include:
                entities.append(include)
                results[_type] = entities
                
        return results

    def clean_json(self, prefix: str, filename: str, data: dict) -> Dict[str, Any]:
        """
        Execute the JSON cleaning workflow.
        
        Args:
            prefix (str): The prefix to use for the file name.
            filename (str): The file name to use for the cleaned data.
            json_data (dict): The JSON data to clean.

        Returns:
            Dict: Cleaned and processed data ready for LLM consumption
        """
        if not filename.endswith("_cleaned.json") and filename.endswith(".json"):
            filename = filename[:-5] + "_cleaned.json"
        elif not filename.endswith("_cleaned.json") and not filename.endswith(".json"):
            filename = filename + "_cleaned.json"
        try: 
            # Get existing data
            final_data = get_json(prefix, filename)
            if len(final_data) > 0:
                return final_data
            
            # Clean the data
            cleaned_data = self._clean_dict(data)
            
            # Parse and extract structured data
            if isinstance(cleaned_data, dict):
                parsed_data = self._parse_clean(cleaned_data, True)
            else:
                # If cleaned_data is not a dict, return empty structure
                parsed_data = {}
            
            # Flatten dict
            final_data = self._flatten_dict(parsed_data)
            save_json(final_data, os.path.join(self.__configuration.data_store_path, prefix), filename) 
            return final_data
            
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "error": f"Invalid JSON data: {str(e)}",
                "cleaned_data": None
            }
        except Exception as e:
            return {
                "status": "error", 
                "error": f"Processing failed: {str(e)}",
                "cleaned_data": None
            }

    def __get_images(self, data: dict, key: str, output_dir: str | None = None, save_images: bool = False) -> List[str]:
        """
        Extracts picture URLs from a nested dictionary.

        Args:
            data (dict): The dictionary containing picture data.
            key (str): The key to extract picture URLs from.
            output_dir (str): The directory to save the images to.
            save_images (bool): Whether to save the images to the output directory.

        Returns:
            list: A list of picture URLs.
        """
        urls = []
        entity_urn = data.get("entityUrn")

        def find_keys_in_dict(d, target_keys):
            """Recursively find target keys in nested dictionary"""
            results = {}
            if isinstance(d, dict):
                for k, v in d.items():
                    if k in target_keys:
                        results[k] = v
                    if isinstance(v, (dict, list)):
                        nested_results = find_keys_in_dict(v, target_keys)
                        results.update(nested_results)
            elif isinstance(d, list):
                for item in d:
                    nested_results = find_keys_in_dict(item, target_keys)
                    results.update(nested_results)
            return results

        # Find rootUrl and artifacts in the entire dictionary structure
        target_data = find_keys_in_dict(data.get(key, {}), ["rootUrl", "artifacts"])
        
        root_url = target_data.get("rootUrl")
        artifacts = target_data.get("artifacts", [])

        if root_url:
            for x in artifacts:
                file_url = x.get("fileIdentifyingUrlPathSegment")
                image_url = f"{root_url}{file_url}"
                urls.append(image_url)
                response = requests.get(image_url)
                if save_images and output_dir:
                    save_image(response.content, output_dir, f"{entity_urn}_{key}_{file_url.split('/')[0]}.png")
        return urls

    def __save_json(
        self, 
        prefix: str, 
        filename: str, 
        data: dict, 
        save_details: bool = False,
    ) -> Dict:
        """Save data to cache.
        
        Args:
            prefix (str): The prefix to use for the file name.
            filename (str): The file name to use for the data.
            data (dict): The data to save.
            save_details (bool): Whether to save the details of the data.

        Returns:
            Dict: The saved data.
        """
        # Save response json
        output_dir = os.path.join(self.__configuration.data_store_path, prefix)
        save_json(data, output_dir, filename + ".json")

        # Save dict data from response json in a separate file
        output_dir_data = os.path.join(output_dir, "data")
        data_dict = data.get("data", {})
        if len(get_json(output_dir_data, f"{filename}_data.json")) == 0:
            save_json(data_dict, output_dir_data, f"{filename}_data.json")

        # Save dict included from response json in a separate file
        output_dir_included = os.path.join(output_dir, "included")
        included = data.get("included", [])
        if len(get_json(output_dir_included, f"{filename}_included.json")) == 0:
            save_json(included, output_dir_included, f"{filename}_included.json")
    
        if save_details:
            for include in included:
                dict_type = include.get("$type")
                dict_label = dict_type.split(".")[-1].strip()
                output_dir_dict_type = os.path.join(output_dir_included, dict_label)
                entity_urn = include.get("entityUrn")
                if len(get_json(output_dir_dict_type, f"{entity_urn}.json")) == 0:
                    save_json(include, output_dir_dict_type, f"{entity_urn}.json")
                for key in ["logo", "backgroundImage", "profile", "backgroundCoverImage"]:
                    if include.get(key):
                        self.__get_images(include, key, output_dir_dict_type, save_images=save_details)
                    else:
                        save_json({}, output_dir_dict_type, f"{entity_urn}.json")
        return data

    @cache(lambda self, method, endpoint, params: method + "_" + endpoint + ("_".join(f"{k}_{v}" for k,v in params.items()) if params else ""), cache_type=DataType.JSON, ttl=datetime.timedelta(days=1))
    def _make_request(
        self,
        method: str, 
        endpoint: str, 
        params: Dict | None = None,
    ) -> Dict:
        """Make HTTP request to LinkedIn API."""        
        # Make request
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                cookies=self.cookies,
                params=params
            )
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"LinkedIn API request failed: {str(e)}")

    def get_organization_public_id(self, url: str) -> str:
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
        
    def get_organization_id(self, linkedin_url: str) -> str:
        """Get organization ID from LinkedIn public ID.
        
        Args:
            linkedin_url (str): LinkedIn organization URL.
        """
        data = self.get_organization_info(linkedin_url)
        elements = data.get('data', {}).get('*elements', [])
        if not elements:
            raise ValueError(f"No organization found for URL: {linkedin_url}")
        return elements[0].replace('urn:li:fs_normalized_company:', '')
    
    def get_organization_info(self, linkedin_url: str, return_cleaned_json: bool = False) -> Dict:
        """Get detailed information about a LinkedIn organization using LinkedIn's native API.
        
        Args:
            linkedin_url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/company/naas-ai/")
            
        Returns:
            Dict: Raw organization data from LinkedIn API
        """
        # Get organization ID
        org_id = self.get_organization_public_id(linkedin_url)
        prefix = os.path.join("get_organization_info", org_id)
        
        # Set up parameters for the request
        params = {
            "decorationId": "com.linkedin.voyager.deco.organization.web.WebFullCompanyMain-33",
            "q": "universalName",
            "universalName": org_id,
        }
        
        endpoint = f"/organization/companies?{urllib.parse.urlencode(params)}"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, org_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, org_id, data)
        return data
    
    def get_profile_public_id(self, linkedin_url: str) -> str:
        """Extract profile ID from LinkedIn URL.
        
        Handles profile URLs with or without the /in/ prefix.
        """
        if "/in/" in linkedin_url:  
            return linkedin_url.rsplit("/in/")[-1].rsplit("/")[0]
        return ""
    
    def get_profile_id(self, linkedin_url: str) -> str:
        """Extract profile ID from LinkedIn URL.
        
        Handles profile URLs with or without the /in/ prefix.
        """
        data = self.get_profile_view(linkedin_url)
        return f"{data.get('data', {}).get('*profile', {}).replace('urn:li:fs_profile:', '')}"
    
    def get_profile_view(self, linkedin_url: str, return_cleaned_json: bool = False) -> Dict:
        """Get profile view for a LinkedIn organization.
        
        Args:
            linkedin_url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")
            
        Returns:
            Dict: Raw profile view data from LinkedIn API
        """
        # Get organization ID
        profile_id = self.get_profile_public_id(linkedin_url)
        prefix = os.path.join("get_profile_view", profile_id)
        
        endpoint = f"/identity/profiles/{profile_id}/profileView"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, profile_id, data)
        return data

    def get_profile_top_card(self, linkedin_url: str, return_cleaned_json: bool = False) -> Dict:
        """Get profile top card information for a LinkedIn profile.
        
        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")
            
        Returns:
            Dict: Raw profile top card data from LinkedIn API
        """
        # Get profile ID
        profile_id = self.get_profile_public_id(linkedin_url)
        prefix = os.path.join("get_profile_top_card", profile_id)
        
        endpoint = f"/graphql?variables=(vanityName:{profile_id})&queryId=voyagerIdentityDashProfiles.0bc93b66ba223b9d30d1cb5c05ff031a"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, profile_id, data)
        return data

    def get_profile_skills(self, linkedin_url: str, return_cleaned_json: bool = False) -> Dict:
        """Get profile skills for a LinkedIn profile.
        
        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")
            
        Returns:
            Dict: Raw profile skills data from LinkedIn API
        """
        # Get profile ID
        profile_id = self.get_profile_public_id(linkedin_url)
        prefix = os.path.join("get_profile_skills", profile_id)
        
        endpoint = f"/identity/profiles/{profile_id}/skillCategory"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, profile_id, data)
        return data
    
    def get_profile_network_info(self, linkedin_url: str, return_cleaned_json: bool = False) -> Dict:
        """Get network information for a LinkedIn profile.
        
        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")
            
        Returns:
            Dict: Raw network information data from LinkedIn API
        """
        # Get profile ID
        profile_id = self.get_profile_public_id(linkedin_url)
        prefix = os.path.join("get_network_info", profile_id)
        
        endpoint = f"/identity/profiles/{profile_id}/networkinfo"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, profile_id, data)
        return data
    
    def get_profile_posts_feed(self, profile_id: str, count: int = 1, return_cleaned_json: bool = False) -> Dict:
        """Get posts feed for a LinkedIn profile.
        
        Args:
            profile_id (str): LinkedIn profile ID (e.g., "ACoAAX0AADoBAAA5V9mHvH1a8_9Nc_fEk3D-wZf4cVU")
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of posts to fetch per request. Defaults to 10.
            limit (int, optional): Maximum number of posts to return. Defaults to -1 (no limit).
            
        Returns:
            Dict: Raw posts feed data from LinkedIn API
        """
        # Get profile ID
        prefix = os.path.join("get_profile_posts_feed", profile_id)
        filename = f"{profile_id}_{count}"

        params = {
            "count": count,
            "includeLongTermHistory": "true", 
            "moduleKey": "member-shares:phone",
            "profileUrn": f"urn:li:fsd_profile:{profile_id}",
            "q": "memberShareFeed",
        }
        endpoint = f"/identity/profileUpdatesV2?{urllib.parse.urlencode(params, doseq=True)}"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, filename, data)
        if return_cleaned_json:
            return self.clean_json(prefix, filename, data)
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
    
    def get_post_stats(self, linkedin_url: str, return_cleaned_json: bool = False) -> Dict:
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
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, activity_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, activity_id, data)
        return data
    
    def get_post_reactions(self, linkedin_url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> Dict:
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
            
        self.__save_json(prefix, filename, all_data)
        if return_cleaned_json:
            return self.clean_json(prefix, filename, all_data)
        return all_data
    
    def get_post_comments(self, linkedin_url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> Dict:
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
            
        self.__save_json(prefix, filename, all_data)
        if return_cleaned_json:
            return self.clean_json(prefix, filename, all_data)
        return all_data
    
    def get_mutual_connexions(
        self, 
        profile_id: str, 
        start: int = 0,
        current_company_id: str = "", 
        return_cleaned_json: bool = False
    ) -> Dict:
        """Get mutual connections for a LinkedIn profile.
        It will return the total number of connections and the first 10 profiles.
        
        Args:
            profile_id (str): LinkedIn profile ID.
            start (int, optional): Start index for pagination. Defaults to 0.
            current_company_id (str, optional): LinkedIn company ID. Defaults to "".
            return_cleaned_json (bool, optional): Whether to return cleaned JSON data. Defaults to False.
        """
        prefix = os.path.join("get_mutual_connexions", profile_id)

        # Full URL with query parameters directly embedded
        endpoint = (
            "/graphql?"
            "queryId=voyagerSearchDashClusters.c0f8645a22a6347486d76d5b9d985fd7&"
            f"variables=(start:{str(start)},"
            "origin:FACETED_SEARCH,"
            "query:(flagshipSearchIntent:SEARCH_SRP,"
            f"queryParameters:List((key:connectionOf,value:List({profile_id})),"
            f"(key:currentCompany,value:List({current_company_id})),"
            "(key:network,value:List(F)),"
            "(key:resultType,value:List(PEOPLE))),"
            "includeFiltersInResponse:false))"
        )
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            cleaned_data = self.clean_json(prefix, profile_id, data)
            total_connections = _.get(data, 'data.data.searchDashClustersByAll.metadata.totalResultCount', 0)
            # Extract only relevant entity information
            entities = []
            for entity in cleaned_data.get('com.linkedin.voyager.dash.search.EntityResultViewModel', []):
                entities.append({
                    'name': _.get(entity, 'title.text'),
                    'headline': _.get(entity, 'primarySubtitle.text'),
                    'location': _.get(entity, 'secondarySubtitle.text'),
                    'profile_url': _.get(entity, 'navigationUrl'),
                    'profile_picture': _.get(entity, 'image.attributes[0].detailData.nonEntityProfilePicture.vectorImage.artifacts[0].fileIdentifyingUrlPathSegment'),
                    'connection_degree': _.get(entity, 'entityCustomTrackingInfo.memberDistance')
                })
            
            final_data = {
                'total_connections': total_connections,
                'connections': entities
            }
            save_json(final_data, os.path.join(self.__configuration.data_store_path, prefix), f"{profile_id}_final_data.json")
            return final_data
        return data
    
def as_tools(configuration: LinkedInIntegrationConfiguration):
    """Convert LinkedIn integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Annotated

    integration = LinkedInIntegration(configuration)

    # class GetOrganizationInfoSchema(BaseModel):
    #     linkedin_url: str = Field(
    #         ..., 
    #         description="LinkedIn organization URL", 
    #         pattern=r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"
    #     )

    class GetProfileSchema(BaseModel):
        linkedin_url: str = Field(
            ..., 
            description="LinkedIn profile URL", 
            pattern=r"https://.+\.linkedin\.[^/]+/in/[^?]+"
        )

    # class GetProfilePostsFeedSchema(BaseModel):
    #     profile_id: str = Field(
    #         ..., 
    #         description="LinkedIn profile URL", 
    #         pattern=r"^ACoAA.+"
    #     )
    #     count: int = Field(
    #         1,
    #         description="Number of posts to fetch", 
    #     )

    # class GetActivitySchema(BaseModel):
    #     linkedin_url: str = Field(
    #         ..., 
    #         description="LinkedIn activity ID extracted from the URL", 
    #     )

    class GetMutualConnectionsSchema(BaseModel):
        profile_id: Annotated[str, Field(
            ...,
            description=(
                "LinkedIn profile ID of the person you want to get mutual connections. "
                "If you don't have the profile ID, use the linkedin_get_profile_id tool to get it."
            ),
            pattern=r"^ACoAA.+"
        )]
        current_company_id: Annotated[str, Field(
            default="",  # 👈 enforce default
            description=(
                "LinkedIn company ID to filter the mutual connections. "
                "If you don't have the company ID, use the linkedin_get_organization_id tool to get it."
            ),
        )]

    return [
        # StructuredTool(
        #     name="linkedin_get_organization_id",
        #     description="Get LinkedIn organization ID for a LinkedIn organization.",
        #     func=lambda linkedin_url: integration.get_organization_id(linkedin_url),
        #     args_schema=GetOrganizationInfoSchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_organization_info",
        #     description="Get organization information for a LinkedIn organization.",
        #     func=lambda linkedin_url: integration.get_organization_info(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetOrganizationInfoSchema
        # ),
        StructuredTool(
            name="linkedin_get_profile_id",
            description="Get LinkedIn unique profile ID for a LinkedIn profile starting with AcoAA.",
            func=lambda linkedin_url: integration.get_profile_id(linkedin_url),
            args_schema=GetProfileSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_top_card",
            description="Get profile top card for a LinkedIn profile, meaning the quick overview information of the profile.",
            func=lambda linkedin_url: integration.get_profile_top_card(linkedin_url, return_cleaned_json=True),
            args_schema=GetProfileSchema
        ),
        # StructuredTool(
        #     name="linkedin_get_profile_view",
        #     description="Get profile view for a LinkedIn organization.",
        #     func=lambda linkedin_url: integration.get_profile_view(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetProfileSchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_profile_skills",
        #     description="Get profile skills for a LinkedIn profile.",
        #     func=lambda linkedin_url: integration.get_profile_skills(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetProfileSchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_profile_network_info",
        #     description="Get network information for a LinkedIn profile.",
        #     func=lambda linkedin_url: integration.get_profile_network_info(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetProfileSchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_profile_posts_feed",
        #     description="Get posts feed for a LinkedIn profile.",
        #     func=lambda profile_id, count: integration.get_profile_posts_feed(profile_id, count, return_cleaned_json=True),
        #     args_schema=GetProfilePostsFeedSchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_post_stats",
        #     description="Get post stats for a LinkedIn activity.",
        #     func=lambda linkedin_url: integration.get_post_stats(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetActivitySchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_post_comments",
        #     description="Get comments for a LinkedIn activity.",
        #     func=lambda linkedin_url: integration.get_post_comments(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetActivitySchema
        # ),
        # StructuredTool(
        #     name="linkedin_get_post_reactions",
        #     description="Get reactions for a LinkedIn activity.",
        #     func=lambda linkedin_url: integration.get_post_reactions(linkedin_url, return_cleaned_json=True),
        #     args_schema=GetActivitySchema
        # ),
        StructuredTool(
            name="linkedin_get_mutual_connexions",
            description="Get mutual connections for a LinkedIn profile.",
            func=lambda profile_id, current_company_id: integration.get_mutual_connexions(profile_id=profile_id, current_company_id=current_company_id, return_cleaned_json=True),
            args_schema=GetMutualConnectionsSchema
        )
    ]