import datetime
import json
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, MutableMapping, Union
import pydash as _
import requests
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
)
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core import logger
from naas_abi_marketplace.applications.linkedin import ABIModule
import time
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
    NaasIntegration,
)

cache = CacheFactory.CacheFS_find_storage(subpath="linkedin")


@dataclass
class LinkedInIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn integration.

    Attributes:
        li_at (str): LinkedIn li_at cookie value for authentication
        JSESSIONID (str): LinkedIn JSESSIONID cookie value for authentication
        profile_url (str): LinkedIn profile URL to use for the integration.
        naas_integration_config (NaasIntegrationConfiguration): Configuration for Naas integration.
        base_url (str): Base URL for LinkedIn API
        datastore_path (str): Path to store cached data
    """

    li_at: str
    JSESSIONID: str
    linkedin_url: str
    naas_integration_config: NaasIntegrationConfiguration
    base_url: str = "https://www.linkedin.com/voyager/api"
    datastore_path: str = field(default_factory=lambda: ABIModule.get_instance().configuration.datastore_path)


class LinkedInIntegration(Integration):
    """LinkedIn API integration client focused on organization information."""

    __configuration: LinkedInIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: LinkedInIntegrationConfiguration):
        """Initialize LinkedIn client with authentication cookies."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__configuration.JSESSIONID = self.__configuration.JSESSIONID.replace(
            '"', ""
        )
        self.__naas_integration: NaasIntegration = NaasIntegration(self.__configuration.naas_integration_config)
        self.__storage_utils: StorageUtils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

        # Initialize cookies and headers
        self.cookies = {
            "li_at": self.__configuration.li_at,
            "JSESSIONID": self.__configuration.JSESSIONID,
        }

        self.headers = {
            "x-li-lan": "en_US",
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "csrf-token": self.__configuration.JSESSIONID,
            "x-restli-protocol-version": "2.0.0",
        }

        self.profile_url = self.__configuration.linkedin_url
        profile_public_id_result = self.get_profile_public_id(self.profile_url)
        public_id_error = profile_public_id_result.get("error")
        if public_id_error:
            raise Exception(f"Failed to fetch LinkedIn profile public ID for URL '{self.profile_url}': {public_id_error}")
        profile_public_id = profile_public_id_result.get("result")
        if not profile_public_id:
            raise Exception(f"LinkedIn profile public ID is empty for URL '{self.profile_url}'")
        self.profile_public_id = profile_public_id

    def _flatten_dict(
        self, data: Union[Dict, Any], parent_key: str = "", sep: str = "_"
    ) -> Dict:
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
            return [
                val for val in (self._clean_dict(x) for x in data) if val is not None
            ]
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
            if _type is None or (
                _type.endswith("View")
                or _type.endswith("Group")
                or _type.endswith("Action")
            ):
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
                            include[key] = picture_urls[
                                -1
                            ]  # Take the last (highest quality) URL

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
            final_data = self.__storage_utils.get_json(prefix, filename)
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
            self.__storage_utils.save_json(
                final_data,
                os.path.join(self.__configuration.datastore_path, prefix),
                filename,
            )
            return final_data

        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "error": f"Invalid JSON data: {str(e)}",
                "cleaned_data": None,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Processing failed: {str(e)}",
                "cleaned_data": None,
            }

    def __get_images(
        self,
        data: dict,
        key: str,
        output_dir: str | None = None,
        save_images: bool = False,
    ) -> List[str]:
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
                    self.__storage_utils.save_image(
                        response.content,
                        output_dir,
                        f"{entity_urn}_{key}_{file_url.split('/')[0]}.png",
                    )
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
        output_dir = os.path.join(self.__configuration.datastore_path, prefix)
        self.__storage_utils.save_json(data, output_dir, filename + ".json")

        # Save dict data from response json in a separate file
        output_dir_data = os.path.join(output_dir, "data")
        data_dict = data.get("data", {})
        if len(self.__storage_utils.get_json(output_dir_data, f"{filename}_data.json")) == 0:
            self.__storage_utils.save_json(data_dict, output_dir_data, f"{filename}_data.json")

        # Save dict included from response json in a separate file
        output_dir_included = os.path.join(output_dir, "included")
        included = data.get("included", [])
        if len(self.__storage_utils.get_json(output_dir_included, f"{filename}_included.json")) == 0:
            self.__storage_utils.save_json(included, output_dir_included, f"{filename}_included.json")

        if save_details:
            for include in included:
                dict_type = include.get("$type")
                dict_label = dict_type.split(".")[-1].strip()
                output_dir_dict_type = os.path.join(output_dir_included, dict_label)
                entity_urn = include.get("entityUrn")
                if len(self.__storage_utils.get_json(output_dir_dict_type, f"{entity_urn}.json")) == 0:
                    self.__storage_utils.save_json(include, output_dir_dict_type, f"{entity_urn}.json")
                for key in [
                    "logo",
                    "backgroundImage",
                    "profile",
                    "backgroundCoverImage",
                ]:
                    if include.get(key):
                        self.__get_images(
                            include, key, output_dir_dict_type, save_images=save_details
                        )
                    else:
                        self.__storage_utils.save_json({}, output_dir_dict_type, f"{entity_urn}.json")
        return data

    @cache(
        lambda self, method, endpoint, params: method
        + "_"
        + self.cookies.get("li_at")
        + "_"
        + self.cookies.get("JSESSIONID")
        + "_"
        + endpoint
        + ("_".join(f"{k}_{v}" for k, v in params.items()) if params else ""),
        cache_type=DataType.JSON,
        ttl=datetime.timedelta(days=1),
    )
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
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": f"LinkedIn API request failed: {str(e)}",
                "request_data": {
                    "url": url,
                    "headers": self.headers,
                    "cookies": self.cookies,
                    "params": params,
                },
                "response_data": {
                    "status_code": response.status_code,
                    "text": response.text,
                },
            }

    def get_organization_id_from_url(self, url: str) -> Dict[str, str]:
        """Get organization ID from LinkedIn organization URL.

        Handles company, school and showcase pages.

        Args:
            url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/company/naas-ai/")

        Returns:
            str: Organization ID
        """
        if "/company/" in url:
            org_id = url.rsplit("/company/")[-1].rsplit("/")[0]
        elif "/school/" in url:
            org_id = url.rsplit("/school/")[-1].rsplit("/")[0]
        elif "/showcase/" in url:
            org_id = url.rsplit("/showcase/")[-1].rsplit("/")[0]
        else:
            return {
                "error": f"LinkedIn organization URL '{url}' not recognized. Must contain /company/, /school/ or /showcase/ in the URL",
            }
        return {"result": org_id}

    def get_organization_id(self, url: str) -> Dict[str, str]:
        """Get organization ID from LinkedIn organization data.

        Args:
            url (str): LinkedIn organization URL.
        """
        data = self.get_organization_info(url)
        elements = data.get("data", {}).get("*elements", [])
        if not elements:
            return {
                "error": f"LinkedIn organization ID not found for URL '{url}'",
            }
        return {"result": elements[0].replace("urn:li:fs_normalized_company:", "")}

    def get_organization_info(
        self, 
        url: str, 
        return_cleaned_json: bool = False
    ) -> Dict:
        """Get detailed information about a LinkedIn organization using LinkedIn's native API.

        Args:
            url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/company/naas-ai/")

        Returns:
            Dict: Raw organization data from LinkedIn API
        """
        # Get organization ID
        org_id_result = self.get_organization_id_from_url(url)
        if org_id_result.get("error"):
            return org_id_result
        
        org_id = org_id_result.get("result")
        if not org_id:
            return {"error": f"LinkedIn organization ID is empty for URL '{url}'"}

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

    def get_profile_id_from_url(self, url: str) -> Dict[str, str]:
        """Extract profile ID from LinkedIn profile URL.

        Handles profile URLs with or without the /in/ prefix.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            Dict: Profile ID
        """
        if "/in/" in url:
            return {"result": url.rsplit("/in/")[-1].rsplit("/")[0]}
        return {"error": f"LinkedIn profile URL '{url}' not recognized. Must contain /in/ in the URL"}
    
    def get_profile_public_id(self, url: str) -> Dict[str, str]:
        """Get profile public ID / public identifier from LinkedIn profile data.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            str: Profile public ID / public identifier
        """
        data = self.get_profile_top_card(url)
        elements = data.get('data', {}).get('data', {}).get('identityDashProfilesByMemberIdentity', {}).get('*elements', [])
        if not elements:
            return {"error": f"LinkedIn profile public ID not found for URL '{url}'"}
        entity_urn = elements[0]
        data_entity = _.find(data.get('included', []), lambda x: x.get('entityUrn') == entity_urn)
        public_identifier = data_entity.get('publicIdentifier') if data_entity else None
        if public_identifier:
            return {"result": public_identifier}
        
        # If not found, get from overflowActionsResolutionResults
        try:
            overflow_actions = data_entity.get('profileStatefulProfileActions', {}).get('overflowActionsResolutionResults', []) if data_entity else []
            share_url = None
            for action in overflow_actions:
                if action.get("shareProfileUrlViaMessage"):
                    share_url = action["shareProfileUrlViaMessage"]
                    break
            if not share_url:
                for action in overflow_actions:
                    if action.get("shareProfileUrl"):
                        share_url = action["shareProfileUrl"]
                        break
            share_url_result = self.get_profile_id_from_url(share_url)
            if share_url_result.get("error"):
                return share_url_result
            return {"result": share_url_result.get("result", "")}
        except Exception:
            return {"error": f"LinkedIn profile public ID not found for URL '{url}'"}

    def get_profile_id(self, url: str) -> Dict[str, str]:
        """Get profile ID from LinkedIn profile data.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            str: Profile ID starting with AcoAA
        """
        data = self.get_profile_top_card(url)
        elements = (
            data.get("data", {})
            .get("data", {})
            .get("identityDashProfilesByMemberIdentity", {})
            .get("*elements", [])
        )
        if not elements:
            logger.warning(f"No profile found for URL: {url}")
            return {"error": f"LinkedIn profile ID not found for URL '{url}'"}
        return {"result": elements[0].replace("urn:li:fsd_profile:", "")}

    def get_profile_top_card(
        self, 
        url: str, 
        return_cleaned_json: bool = False
    ) -> Dict:
        """Get profile top card information for a LinkedIn profil url.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            Dict: Raw profile top card data from LinkedIn API
        """
        # Get profile ID
        profile_id_result = self.get_profile_id_from_url(url)
        if profile_id_result.get("error"):
            return profile_id_result
        
        profile_id = profile_id_result.get("result")
        if not profile_id:
            return {"error": f"LinkedIn profile ID is empty for URL '{url}'"}
        
        if profile_id.startswith('AcoAA'):
            return {"error": f"LinkedIn profile ID '{profile_id}' starts with AcoAA. LinkedIn profile URL is not valid: {url}"}
        
        prefix = os.path.join("get_profile_top_card", profile_id)
        endpoint = f"/graphql?variables=(vanityName:{profile_id})&queryId=voyagerIdentityDashProfiles.0bc93b66ba223b9d30d1cb5c05ff031a"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, profile_id, data)
        return data

    def get_profile_data(
        self,
        url: str,
        profile_type: str = "skills",
        locale: str = "en_US",
        return_cleaned_json: bool = False,
    ) -> Dict:
        """Get profile skills for a LinkedIn profile.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            Dict: Raw profile skills data from LinkedIn API
        """
        # Get profile ID
        profile_id_result = self.get_profile_id(url)
        if profile_id_result.get("error"):
            return profile_id_result
        profile_id = profile_id_result.get("result")
        if not profile_id:
            return {"error": f"LinkedIn profile ID is empty for URL '{url}'"}
        
        profile_public_id_result = self.get_profile_public_id(url)
        if profile_public_id_result.get("error"):
            return profile_public_id_result
        profile_public_id = profile_public_id_result.get("result")
        if not profile_public_id:
            return {"error": f"LinkedIn profile public ID is empty for URL '{url}'"}
        
        prefix = os.path.join("get_profile_data", profile_public_id, profile_type)
        endpoint = f"/graphql?variables=(profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id},sectionType:{profile_type},locale:{locale})&queryId=voyagerIdentityDashProfileComponents.c5d4db426a0f8247b8ab7bc1d660775a"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, profile_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, profile_id, data)
        return data

    def get_profile_skills(
        self, url: str, return_cleaned_json: bool = False
    ) -> Dict:
        """Get profile skills for a LinkedIn profile.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            Dict: Raw profile skills data from LinkedIn API
        """
        return self.get_profile_data(
            url, 
            profile_type="skills", 
            return_cleaned_json=return_cleaned_json
        )

    def get_profile_experience(
        self, url: str, return_cleaned_json: bool = False
    ) -> Dict:
        """Get profile experience for a LinkedIn profile.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            Dict: Raw profile experience data from LinkedIn API
        """
        return self.get_profile_data(
            url,
            profile_type="experience",
            return_cleaned_json=return_cleaned_json,
        )

    def get_profile_education(
        self, url: str, return_cleaned_json: bool = False
    ) -> Dict:
        """Get profile experience for a LinkedIn profile.

        Args:
            url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/florent-ravenel/")

        Returns:
            Dict: Raw profile experience data from LinkedIn API
        """
        return self.get_profile_data(
            url,
            profile_type="education",
            return_cleaned_json=return_cleaned_json,
        )

    def get_date_from_token(self, token):
        import base64
        from datetime import datetime
        from zoneinfo import ZoneInfo

        date = None
        epoch_str = str(base64.b64decode(token)).split("-")[-1][:-1]
        date = datetime.fromtimestamp(
            int(epoch_str) / 1000.0, ZoneInfo("Europe/Paris")
        ).strftime("%Y-%m-%dT%H:%M:%S%z")
        return date

    def get_profile_posts_feed(
        self,
        url: str,
        start: int = 0,
        count: int = 1,
        pagination_token: str | None = None,
        return_cleaned_json: bool = False,
    ) -> Dict:
        """Get posts feed for a LinkedIn profile.

        Args:
            profile_id (str): LinkedIn profile URL or ID
            count (int, optional): Number of posts to fetch. Defaults to 1.
            return_cleaned_json (bool, optional): Whether to return cleaned JSON. Defaults to False.

        Returns:
            Dict: Raw posts feed data from LinkedIn API
        """
        profile_id_result = self.get_profile_id(url)
        if profile_id_result.get("error"):
            return profile_id_result
        profile_id = profile_id_result.get("result")
        if not profile_id:
            return {"error": f"LinkedIn profile ID is empty for URL '{url}'"}
        
        profile_public_id_result = self.get_profile_public_id(url)
        if profile_public_id_result.get("error"):
            return profile_public_id_result
        profile_public_id = profile_public_id_result.get("result")
        if not profile_public_id:
            return {"error": f"LinkedIn profile public ID is empty for URL '{url}'"}

        endpoint = f"/graphql?includeWebMetadata=true&variables=(start:{start},count:{count},profileUrn:urn%3Ali%3Afsd_profile%3A{profile_id})&queryId=voyagerFeedDashProfileUpdates.80d5abb3cd25edff72c093a5db696079"
        data = self._make_request(method="GET", endpoint=endpoint)

        assert data["data"]["data"] is not None, data
        assert (
            data["data"]["data"]["feedDashProfileUpdatesByMemberShareFeed"]["*elements"]
            is not None
        ), data
        activity_id = (
            data["data"]["data"]["feedDashProfileUpdatesByMemberShareFeed"][
                "*elements"
            ][0]
            .split("urn:li:activity:")[-1]
            .split(",")[0]
        )

        assert (
            data["data"]["data"]["feedDashProfileUpdatesByMemberShareFeed"]["metadata"][
                "paginationToken"
            ]
            is not None
        ), data
        pagination_token = data["data"]["data"][
            "feedDashProfileUpdatesByMemberShareFeed"
        ]["metadata"]["paginationToken"]
        date_published = self.get_date_from_token(pagination_token)
        filename = f"profile_{profile_id}_post_{activity_id}"
        prefix = os.path.join(
            "get_profile_posts_feed",
            profile_public_id,
            f"{date_published}_{activity_id}",
        )
        self.__save_json(prefix, filename, data)
        if return_cleaned_json:
            return self.clean_json(prefix, filename, data)
        return data

    def get_activity_id_from_url(self, url: str) -> Dict:
        """Extract activity ID from LinkedIn URL.

        Handles activity URLs with or without the -activity- or :activity: prefix.
        """
        if "-activity-" in url:
            return {"result": url.split("-activity-")[-1].split("-")[0]}
        elif ":activity:" in url:
            return {"result": url.split(":activity:")[-1].split("/")[0]}
        return {"error": f"LinkedIn activity ID not found for URL '{url}'"}

    def get_post_stats(
        self, url: str, return_cleaned_json: bool = False
    ) -> Dict:
        """Get activity for a LinkedIn activity.

        Args:
            url (str): LinkedIn activity URL. It must contain -activity- in the URL.

        Returns:
            Dict: Raw post stats data from LinkedIn API
        """
        # Get activity ID
        activity_id_result = self.get_activity_id_from_url(url)
        if activity_id_result.get("error"):
            return activity_id_result
        activity_id = activity_id_result.get("result")
        if not activity_id:
            return {"error": f"LinkedIn activity ID is empty for URL '{url}'"}
        
        prefix = os.path.join("get_post_stats", activity_id)

        endpoint = f"/feed/updates/urn:li:activity:{activity_id}"
        data = self._make_request(method="GET", endpoint=endpoint)
        self.__save_json(prefix, activity_id, data)
        if return_cleaned_json:
            return self.clean_json(prefix, activity_id, data)
        return data

    def get_post_reactions(
        self,
        url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        return_cleaned_json: bool = False,
    ) -> Dict:
        """Get reactions for a LinkedIn post.

        Args:
            activity_id (str): LinkedIn activity ID.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of reactions to fetch per request. Defaults to 100.
            limit (int, optional): Maximum number of reactions to return. Defaults to -1 (no limit).
        """
        # Get activity ID
        activity_id_result = self.get_activity_id_from_url(url)
        if activity_id_result.get("error"):
            return activity_id_result
        activity_id = activity_id_result.get("result")
        if not activity_id:
            return {"error": f"LinkedIn activity ID is empty for URL '{url}'"}
        
        prefix = os.path.join("get_post_reactions", activity_id)
        filename = f"post_reactions_{activity_id}_{start}_{count}"

        variables = {
            "start": start,
            "count": count,
            "threadUrn": f"urn:li:activity:{activity_id}",
        }
        endpoint = f"/graphql?variables={urllib.parse.quote(str(variables))}&queryId=voyagerSocialDashReactions.41ebf31a9f4c4a84e35a49d5abc9010b"

        all_data = None
        while True:
            if limit != -1 and limit < count:
                count = limit

            variables["start"] = start
            variables["count"] = count
            filename = f"{activity_id}_{start}_{count}"

            data = self._make_request(
                prefix=prefix, filename=filename, method="GET", endpoint=endpoint
            )

            if not all_data:
                all_data = data
            else:
                all_data["included"].extend(data.get("included", []))
                all_data["data"]["*elements"].extend(data["data"]["*elements"])

            total = (
                data.get("data", {})
                .get("data", {})
                .get("socialDashReactionsByReactionType", {})
                .get("paging", {})
                .get("total", 0)
            )
            fetched = start + len(
                data.get("data", {})
                .get("data", {})
                .get("socialDashReactionsByReactionType", {})
                .get("*elements", [])
            )

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

    def get_post_comments(
        self,
        url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        return_cleaned_json: bool = False,
    ) -> Dict:
        """Get comments for a LinkedIn post.

        Args:
            url (str): LinkedIn post URL.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of comments to fetch per request. Defaults to 100.
            limit (int, optional): Maximum number of comments to return. Defaults to -1 (no limit).
            return_cleaned_json (bool, optional): Whether to return cleaned JSON. Defaults to False.
        """
        # Get activity ID
        activity_id_result = self.get_activity_id_from_url(url)
        if activity_id_result.get("error"):
            return activity_id_result
        activity_id = activity_id_result.get("result")
        if not activity_id:
            return {"error": f"LinkedIn activity ID is empty for URL '{url}'"}
        
        prefix = os.path.join("get_post_comments", activity_id)
        filename = f"post_comments_{activity_id}_{start}_{count}"

        # Build GraphQL query parameters
        variables = {
            "start": start,
            "count": count,
            "socialDetailUrn": f"urn:li:fsd_socialDetail:(urn:li:activity:{activity_id},urn:li:activity:{activity_id},urn:li:highlightedReply:-)",
            "sortOrder": "REVERSE_CHRONOLOGICAL",
        }

        endpoint = f"/graphql?variables={urllib.parse.quote(str(variables))}&queryId=voyagerSocialDashComments.afec6d88d7810d45548797a8dac4fb87"

        all_data = None
        while True:
            if limit != -1 and limit < count:
                count = limit

            variables["start"] = start
            variables["count"] = count
            filename = f"{activity_id}_{start}_{count}"

            data = self._make_request(
                prefix=prefix, filename=filename, method="GET", endpoint=endpoint
            )

            if not all_data:
                all_data = data
            else:
                all_data["included"].extend(data.get("included", []))
                all_data["data"]["socialDashCommentsBySocialDetail"][
                    "*elements"
                ].extend(data["data"]["socialDashCommentsBySocialDetail"]["*elements"])

            total = (
                data.get("data", {})
                .get("socialDashCommentsBySocialDetail", {})
                .get("paging", {})
                .get("total", 0)
            )
            fetched = start + len(
                data.get("data", {})
                .get("socialDashCommentsBySocialDetail", {})
                .get("*elements", [])
            )

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

    def get_post_reposts(
        self,
        url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        return_cleaned_json: bool = False,
    ) -> Dict:
        """Get reposts for a LinkedIn activity.

        Args:
            url (str): LinkedIn post URL.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of reposts to fetch per request. Defaults to 100.
            limit (int, optional): Maximum number of reposts to return. Defaults to -1 (no limit).
            return_cleaned_json (bool, optional): Whether to return cleaned JSON. Defaults to False.
        """
        # Get activity ID
        activity_id_result = self.get_activity_id_from_url(url)
        if activity_id_result.get("error"):
            return activity_id_result
        activity_id = activity_id_result.get("result")
        if not activity_id:
            return {"error": f"LinkedIn activity ID is empty for URL '{url}'"}
        
        prefix = os.path.join("get_post_reposts", activity_id)
        filename = f"post_repost_{activity_id}_{start}_{count}"

        # Build GraphQL query parameters
        variables = {
            "start": start,
            "count": count,
            "targetUrn": f"urn:li:share:{activity_id}",
        }

        endpoint = f"/graphql?includeWebMetadata=true&variables={urllib.parse.quote(str(variables))}&queryId=voyagerFeedDashReshareFeed.47df8432a2f218e699221ed615e04842"

        all_data = None
        while True:
            if limit != -1 and limit < count:
                count = limit

            variables["start"] = start
            variables["count"] = count
            filename = f"{activity_id}_{start}_{count}"

            data = self._make_request(
                prefix=prefix, filename=filename, method="GET", endpoint=endpoint
            )

            if not all_data:
                all_data = data
            else:
                all_data["data"]["data"]["feedDashReshareFeedByReshareFeed"][
                    "*elements"
                ].extend(
                    data["data"]["data"]["feedDashReshareFeedByReshareFeed"][
                        "*elements"
                    ]
                )

            total = (
                data.get("data", {})
                .get("data", {})
                .get("feedDashReshareFeedByReshareFeed", {})
                .get("paging", {})
                .get("total", 0)
            )
            fetched = start + len(
                data.get("data", {})
                .get("data", {})
                .get("feedDashReshareFeedByReshareFeed", {})
                .get("*elements", [])
            )

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
    
    def __get_people_results(self, cleaned_data: dict, entities: list) -> list:
        """Get people results from LinkedIn data.

        Args:
            cleaned_data (dict): Cleaned LinkedIn data.
        """
        for entity in cleaned_data.get(
            "com.linkedin.voyager.dash.search.EntityResultViewModel", []
        ):
            navigation_url = _.get(entity, "navigationUrl")
            profile_url = navigation_url.split("?")[0]
            public_id = profile_url.split("/")[-1]
            profile_id = navigation_url.split("miniProfile%3")[1]
            entities.append(
                {
                    "id": profile_id,
                    "public_id": public_id,
                    "name": _.get(entity, "title.text"),
                    "headline": _.get(entity, "primarySubtitle.text"),
                    "location": _.get(entity, "secondarySubtitle.text"),
                    "profile_url": profile_url,
                    "profile_picture": _.get(
                        entity,
                        "image.attributes[0].detailData.nonEntityProfilePicture.vectorImage.artifacts[0].fileIdentifyingUrlPathSegment",
                    ),
                    "connection_degree": _.get(
                        entity, "entityCustomTrackingInfo.memberDistance"
                    ),
                }
            )
        return entities
    
    def __export_excel(
        self, 
        entities: list, 
        prefix: str,
        file_name: str, 
        sheet_name: str = "EXPORT_LINKEDIN",
        linkedin_profile_id: str | None = None,
        connections_distance: str | None = None,
        linkedin_organization_id: str | None = None,
    ) -> str:
        """Export entities to Excel.

        Args:
            entities (list): List of entities to export.
            filename (str): Filename to export the Excel file.
        """
        import pandas as pd
        from io import BytesIO

        if len(entities) == 0:
            return ""

        df = pd.DataFrame(entities)
        df["init_profile_id"] = self.profile_public_id
        if linkedin_profile_id:
            df["linkedin_profile_id_parameter"] = linkedin_profile_id
        if connections_distance:
            df["connections_distance_parameter"] = connections_distance
        if linkedin_organization_id:
            df["linkedin_organization_id_parameter"] = linkedin_organization_id

        self.__storage_utils.save_excel(
            df,
            os.path.join(self.__configuration.datastore_path, prefix),
            file_name,
            sheet_name,
            copy=False,
        )
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, sheet_name=sheet_name)
        excel_buffer.seek(0)
        asset = self.__naas_integration.upload_asset(
            data=excel_buffer.getvalue(),
            prefix=os.path.join(self.__configuration.datastore_path, prefix),
            object_name=file_name,
            return_url=True,
        )
        return asset.get("asset_url", "")
    
    @cache(
        lambda self, profile_url, organization_url, connection_distance: profile_url + "_" + connection_distance + "_" + (str(organization_url) if organization_url else "all"),
        cache_type=DataType.JSON,
        ttl=datetime.timedelta(days=1),
    )
    def get_mutual_connexions(
        self,
        profile_url: str,
        connection_distance: str = "F",
        organization_url: str | None = None,
        start: int = 0,
        count: int = 50,
        limit: int = 1000,
        query_id: str = "voyagerSearchDashClusters.ef3d0937fb65bd7812e32e5a85028e79",
    ) -> Dict:
        """Get mutual connections for a LinkedIn profile.
        It will return the total number of connections and the connections.

        Args:
            profile_url (str): LinkedIn profile URL.
            connection_distance (str, optional): Connection distance. Defaults to "F" for "First Degree", "S" for "Second Degree", "O" for "Others".
            organization_url (str, optional): LinkedIn organization URL to filter the mutual connections.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of connections to fetch per request. Defaults to 50.
            limit (int, optional): Maximum number of connections to return. Defaults to 1000.
            query_id (str, optional): Query ID generated by LinkedIn to use for the request. We can't generate it ourselves so it might needs to be updated if LinkedIn rotates it.
        """
        # Get profile ID
        profile_id_result = self.get_profile_id(profile_url)
        if profile_id_result.get("error"):
            return profile_id_result
        profile_id = profile_id_result.get("result")
        if not profile_id:
            return {"error": f"LinkedIn profile ID is empty for URL '{profile_url}'"}

        # Get profile public ID
        profile_public_id_result = self.get_profile_public_id(profile_url)
        if profile_public_id_result.get("error"):
            return profile_public_id_result
        profile_public_id = profile_public_id_result.get("result")
        if not profile_public_id:
            return {"error": f"LinkedIn profile public ID is empty for URL '{profile_url}'"}
        
        prefix = os.path.join("get_mutual_connexions", self.profile_public_id, profile_public_id, connection_distance)
        filename = f"get_mutual_connexions_{profile_public_id}_{connection_distance}"

        if organization_url is not None:
            organization_id_result = self.get_organization_id(organization_url)
            if organization_id_result.get("error"):
                return organization_id_result
            organization_id = organization_id_result.get("result")
            if not organization_id:
                return {"error": f"LinkedIn organization ID is empty for URL '{organization_url}'"}
            organization_public_id_result = self.get_organization_id_from_url(organization_url)
            if organization_public_id_result.get("error"):
                return organization_public_id_result
            organization_public_id = organization_public_id_result.get("result")
            if not organization_public_id:
                return {"error": f"LinkedIn organization public ID is empty for URL '{organization_url}'"}
            prefix = os.path.join(prefix, organization_public_id)
            filename += f"_{organization_public_id}"
        else:
            organization_id = ""
            organization_public_id = ""
            prefix = os.path.join(prefix, "_all")

        final_filename = filename
        entities: list = []
        while True:
            print(f"Getting mutual connections for profile '{profile_url}' with connection distance '{connection_distance}' starting from {start} and count {count}")
            endpoint = (
                "/graphql?"
                f"queryId={query_id}&"
                f"variables=(start:{str(start)},count:{str(count)},"
                "origin:FACETED_SEARCH,"
                "query:(flagshipSearchIntent:SEARCH_SRP,"
                f"queryParameters:List((key:connectionOf,value:List({profile_id})),"
                f"(key:currentCompany,value:List({organization_id})),"
                f"(key:network,value:List({connection_distance})),"
                "(key:resultType,value:List(PEOPLE))),"
                "includeFiltersInResponse:false))"
            )
            data = self._make_request(method="GET", endpoint=endpoint)
            self.__save_json(os.path.join(prefix, "pages"), f"{filename}_{start}_{count}.json", data)
            cleaned_data = self.clean_json(os.path.join(prefix, "pages"), f"{filename}_{start}_{count}.json", data)
            entities = self.__get_people_results(cleaned_data, entities)

            total_connections = _.get(
                data, "data.data.searchDashClustersByAll.metadata.totalResultCount", 0
            )
            print(f"Total connections: {total_connections}")
            print(f"Entities found: {len(entities)}")
            if start + count >= total_connections or len(entities) >= limit:
                break
            print(f"Found {len(entities)} connections out of {total_connections}")
            time.sleep(1)
            start += count

        final_data = {
            "total_connections": total_connections,
            "connections_returned": len(entities),
            "connections": entities,
        }
        self.__storage_utils.save_json(
            final_data,
            os.path.join(self.__configuration.datastore_path, prefix),
            final_filename + ".json",
        )
        print(f"Exporting Excel for profile '{profile_url}' with connection distance '{connection_distance}' and organization '{organization_url}'")
        excel_url = self.__export_excel(
            entities, 
            prefix, 
            f"{self.profile_public_id}_{final_filename}.xlsx",
            linkedin_profile_id=profile_public_id,
            connections_distance=connection_distance,
            linkedin_organization_id=organization_public_id,
        )
        print("Downloading Excel file from URL: ", excel_url)
        final_data["excel_url"] = excel_url
        return final_data

    
    @cache(
        lambda self, connection_distance, organization_url: connection_distance + "_" + organization_url,
        cache_type=DataType.JSON,
        ttl=datetime.timedelta(days=1),
    )
    def search_people(
        self,
        connection_distance: str = "F",
        organization_url: str | None = None,
        location: str | None = None,
        start: int = 0,
        count: int = 50,
        limit: int = 1000,
        query_id: str = "voyagerSearchDashClusters.c0f8645a22a6347486d76d5b9d985fd7",
    ) -> Dict:
        """Search for people on LinkedIn.
        It will return the total number of people found and the people.

        Args:
            connection_distance (str, optional): Connection distance. Defaults to "F" for First Degree, "S" for Second Degree, "O" for Others.
            organization_url (str, optional): LinkedIn organization URL to filter the people.
            location (str, optional): Location to filter the people.
            start (int, optional): Start index for pagination. Defaults to 0.
            count (int, optional): Number of people to fetch per request. Defaults to 50.
            limit (int, optional): Maximum number of people to return. Defaults to 1000.
            query_id (str, optional): Query ID generated by LinkedIn to use for the request. We can't generate it ourselves so it might needs to be updated if LinkedIn rotates it.
        """
        prefix = os.path.join("search_people", self.profile_public_id, connection_distance)
        filename = f"search_people_{connection_distance}"

        # Get organization ID
        if organization_url is not None:
            organization_id_result = self.get_organization_id(organization_url)
            if organization_id_result.get("error"):
                return organization_id_result
            organization_id = organization_id_result.get("result")
            if not organization_id:
                return {"error": f"LinkedIn organization ID is empty for URL '{organization_url}'"}
            organization_public_id_result = self.get_organization_id_from_url(organization_url)
            if organization_public_id_result.get("error"):
                return organization_public_id_result
            organization_public_id = organization_public_id_result.get("result")
            if not organization_public_id:
                return {"error": f"LinkedIn organization public ID is empty for URL '{organization_url}'"}
            prefix = os.path.join(prefix, organization_public_id)
            filename += f"_{organization_public_id}"
        else:
            organization_id = ""
            prefix = os.path.join(prefix, "_all")

        # Get location ID
        location_id: str = ""
        if location is not None:
            MAPPING_LOCATION_TO_ID: dict[str, str] = {
                "France": "105015875",
            }
            location_id_from_map = MAPPING_LOCATION_TO_ID.get(location)
            if not location_id_from_map:
                print(f"Location '{location}' not found in mapping")
            else:
                location_id = location_id_from_map
                prefix = os.path.join(prefix, location_id)
                filename += f"_{location_id}"

        final_filename = filename
        entities: list = []
        while True:
            print(f"Searching for people with connection distance '{connection_distance}' starting from {start} and count {count}")
            endpoint = (
                "/graphql?"
                f"queryId={query_id}&"
                f"variables=(start:{str(start)},count:{str(count)},"
                "origin:FACETED_SEARCH,"
                "query:(flagshipSearchIntent:SEARCH_SRP,"
                f"queryParameters:List((key:network,value:List({connection_distance})),"
                f"(key:currentCompany,value:List({organization_id})),"
                f"(key:geoUrn,value:List({location_id})),"
                "(key:resultType,value:List(PEOPLE))),"
                "includeFiltersInResponse:false))"
            )
            data = self._make_request(method="GET", endpoint=endpoint)
            self.__save_json(os.path.join(prefix, "pages"), f"{filename}_{start}_{count}.json", data)
            cleaned_data = self.clean_json(os.path.join(prefix, "pages"), f"{filename}_{start}_{count}.json", data)
            entities = self.__get_people_results(cleaned_data, entities)

            total_connections = _.get(
                data, "data.data.searchDashClustersByAll.metadata.totalResultCount", 0
            )
            print(f"Total connections: {total_connections}")
            print(f"Entities found: {len(entities)}")
            if start + count >= total_connections or len(entities) >= limit:
                break
            print(f"Found {len(entities)} connections out of {total_connections}")
            time.sleep(1)
            start += count

        final_data = {
            "total_connections": total_connections,
            "connections_returned": len(entities),
            "connections": entities,
        }
        self.__storage_utils.save_json(
            final_data,
            os.path.join(self.__configuration.datastore_path, prefix),
            final_filename,
        )

        print(f"Exporting Excel for people with connection distance '{connection_distance}' starting from {start} and count {count}")
        excel_url = self.__export_excel(
            entities, 
            prefix, 
            f"{self.profile_public_id}_{final_filename}.xlsx",
            connections_distance=connection_distance,
            linkedin_organization_id=organization_public_id,
        )
        print("Downloading Excel file from URL: ", excel_url)
        final_data["excel_url"] = excel_url
        return final_data


def as_tools(configuration: LinkedInIntegrationConfiguration):
    """Convert LinkedIn integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Annotated, Optional

    integration = LinkedInIntegration(configuration)

    class GetOrganizationInfoSchema(BaseModel):
        url: str = Field(
            ...,
            description="LinkedIn organization URL",
            pattern=r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+",
        )

    class GetProfileSchema(BaseModel):
        url: str = Field(
            ...,
            description="LinkedIn profile URL",
            pattern=r"https://.+\.linkedin\.[^/]+/in/[^?]+",
        )

    class GetProfilePostsFeedSchema(BaseModel):
        url: str = Field(
            ...,
            description="LinkedIn profile URL",
            pattern=r"https://.+\.linkedin\.[^/]+/in/[^?]+",
        )
        count: int = Field(
            1,
            description="Number of posts to fetch",
        )

    class GetActivitySchema(BaseModel):
        url: str = Field(
            ...,
            description="LinkedIn activity ID extracted from the URL",
        )

    class GetMutualConnectionsSchema(BaseModel):
        profile_url: Annotated[
            str,
            Field(
                ...,
                description=(
                    "LinkedIn profile URL of the person you want to get mutual connections."
                ),
                pattern=r"https://.+\.linkedin\.[^/]+/in/[^?]+",
            ),
        ]
        connection_distance: Annotated[
            str,
            Field(
                description="Connection distance. F for First Degree, S for Second Degree, O for Others.",
                pattern=r"^[FSO]$",
            ),
        ] = "F"
        organization_url: Optional[Annotated[
            str,
            Field(
                description=(
                    "LinkedIn organization URL to filter the mutual connections."
                ),
                pattern=r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+",
            ),
        ]] = None

    class SearchPeopleSchema(BaseModel):
        connection_distance: Annotated[
            str,
            Field(
                description="Connection distance. F for First Degree, S for Second Degree, O for Others.",
                pattern=r"^[FSO]$",
            ),
        ] = "F"
        organization_url: Optional[Annotated[
            str,
            Field(
                description=(
                    "LinkedIn organization URL to filter the people."
                ),
                pattern=r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+",
            ),
        ]] = None
        location: Optional[Annotated[
            str,
            Field(
                description="Location to filter the people.",
            ),
        ]] = None

    return [
        StructuredTool(
            name="linkedin_get_organization_info",
            description="Get organization information for a LinkedIn organization.",
            func=lambda url: integration.get_organization_info(
                url, return_cleaned_json=True
            ),
            args_schema=GetOrganizationInfoSchema,
        ),
        StructuredTool(
            name="linkedin_get_profile_top_card",
            description="Get profile top card for a LinkedIn profile, meaning the quick overview information of the profile.",
            func=lambda url: integration.get_profile_top_card(
                url, return_cleaned_json=True
            ),
            args_schema=GetProfileSchema,
        ),
        StructuredTool(
            name="linkedin_get_profile_skills",
            description="Get profile skills for a LinkedIn profile.",
            func=lambda url: integration.get_profile_skills(
                url, return_cleaned_json=True
            ),
            args_schema=GetProfileSchema,
        ),
        StructuredTool(
            name="linkedin_get_profile_experience",
            description="Get profile experience for a LinkedIn profile.",
            func=lambda url: integration.get_profile_experience(
                url, return_cleaned_json=True
            ),
            args_schema=GetProfileSchema,
        ),
        StructuredTool(
            name="linkedin_get_profile_education",
            description="Get profile education for a LinkedIn profile.",
            func=lambda url: integration.get_profile_education(
                url, return_cleaned_json=True
            ),
            args_schema=GetProfileSchema,
        ),
        StructuredTool(
            name="linkedin_get_profile_posts_feed",
            description="Get posts feed for a LinkedIn profile.",
            func=lambda url, count: integration.get_profile_posts_feed(
                url, count, return_cleaned_json=True
            ),
            args_schema=GetProfilePostsFeedSchema,
        ),
        StructuredTool(
            name="linkedin_get_post_comments",
            description="Get comments for a LinkedIn activity.",
            func=lambda url: integration.get_post_comments(
                url, return_cleaned_json=True
            ),
            args_schema=GetActivitySchema,
        ),
        StructuredTool(
            name="linkedin_get_post_reactions",
            description="Get reactions for a LinkedIn activity.",
            func=lambda url: integration.get_post_reactions(
                url, return_cleaned_json=True
            ),
            args_schema=GetActivitySchema,
        ),
        StructuredTool(
            name="linkedin_get_post_reposts",
            description="Get reposts for a LinkedIn activity.",
            func=lambda url: integration.get_post_reposts(
                url, return_cleaned_json=True
            ),
            args_schema=GetActivitySchema,
        ),
        StructuredTool(
            name="linkedin_get_mutual_connexions",
            description="Get mutual connections for a LinkedIn profile.",
            func=lambda **kwargs: integration.get_mutual_connexions(**kwargs),
            args_schema=GetMutualConnectionsSchema,
        ),
        StructuredTool(
            name="linkedin_search_people",
            description="Search for people on LinkedIn.",
            func=lambda **kwargs: integration.search_people(**kwargs),
            args_schema=SearchPeopleSchema,
        ),
    ]
