from typing import Dict, List, Optional
import requests
from datetime import datetime
from dataclasses import dataclass
from pydantic import BaseModel, Field
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
import pandas as pd
import time
from abi import logger

LOGO_URL = "https://logo.clearbit.com/linkedin.com"

@dataclass
class LinkedInIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn integration.
    
    Attributes:
        li_at (str): LinkedIn li_at cookie value for authentication
        JSESSIONID (str): LinkedIn JSESSIONID cookie value for authentication
        base_url (str): Base URL for LinkedIn API
        custom_api_url (str): Custom API URL for enhanced LinkedIn operations
    """
    li_at: str
    JSESSIONID: str
    base_url: str = "https://www.linkedin.com/voyager/api"
    custom_api_url: str = "https://3hz1hdpnlf.execute-api.eu-west-1.amazonaws.com/prod"

class LinkedInIntegration(Integration):
    """LinkedIn API integration client.
    
    This integration provides methods to interact with LinkedIn's API endpoints. Using the custom API maintained by the team.
    """

    __configuration: LinkedInIntegrationConfiguration

    def __init__(self, configuration: LinkedInIntegrationConfiguration):
        """Initialize LinkedIn client with authentication cookies."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        # Initialize cookies and headers
        self.cookies = {
            "li_at": self.__configuration.li_at,
            "JSESSIONID": f'"{self.__configuration.JSESSIONID}"'
        }
        
        self.headers = {
            "X-Li-Lang": "en_US",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "Cache-Control": "no-cache", 
            "csrf-Token": self.__configuration.JSESSIONID,
            "X-Requested-With": "XMLHttpRequest",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        self.custom_headers = {
            "Content-Type": "application/json"
        }

    def manage_api_error(self, res):
        """Manage API error responses.
        
        Args:
            res (Response): Response object from requests
            
        Raises:
            TooManyRedirects: When status code is 302 (redirect)
            BaseException: For all other non-200 status codes
        """
        if res.status_code != 200:
            if int(res.status_code) == 302:
                raise requests.TooManyRedirects(res.status_code, res.text)
            else:
                raise BaseException(res.status_code, res.text)

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
            if use_custom_api:
                self.manage_api_error(response)  # Add error management before raise_for_status
                response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"LinkedIn API request failed: {str(e)}")
        
    def get_public_profile_id(self, linkedin_url: str) -> str:
        """Extract profile ID from LinkedIn profile URL."""
        return linkedin_url.rsplit("/in/")[-1].rsplit("/")[0]
    
    def get_profile_id(self, linkedin_url: str) -> str:
        public_id = self.get_public_profile_id(linkedin_url)
        res = requests.get(
            f"https://www.linkedin.com/voyager/api/identity/profiles/{public_id}",
            cookies=self.cookies,
            headers=self.headers,
        )
        # Check if requests is successful
        try:
            res.raise_for_status()
            res_json = res.json()
            return (
                res_json.get("data", {})
                .get("entityUrn")
                .replace("urn:li:fs_profile:", "")
            )
        except requests.HTTPError as e:
            return e

    def get_profile_view(self, linkedin_url: str = None, sleep: bool = True) -> pd.DataFrame:
        """Get profile view information for a LinkedIn profile.

        Args:
            linkedin_url (str, optional): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username/"). Defaults to None.
            sleep (bool, optional): Whether to sleep between requests. Defaults to True.
        """

        # Get profile info
        profile_id = self.get_public_profile_id(linkedin_url)
        endpoint = f"/identity/profiles/{profile_id}/profileView"
        return self._make_request("GET", endpoint)
    
    def get_profile_network(self, linkedin_url: str = None, sleep: bool = True) -> pd.DataFrame:
        """Get network information for a LinkedIn profile.

        Args:
            linkedin_url (str, optional): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username/"). Defaults to None.
            sleep (bool, optional): Whether to sleep between requests. Defaults to True.
        """

        # Get profile info
        profile_id = self.get_public_profile_id(linkedin_url)
        endpoint = f"/identity/profiles/{profile_id}/networkinfo"
        return self._make_request("GET", endpoint)

    def get_profile_contact(self, linkedin_url: str = None, sleep: bool = True) -> pd.DataFrame:
        """Get contact information for a LinkedIn profile.

        Args:
            linkedin_url (str, optional): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username/"). Defaults to None.
            sleep (bool, optional): Whether to sleep between requests. Defaults to True.
        """

        # Get profile info
        profile_id = self.get_public_profile_id(linkedin_url)
        endpoint = f"/identity/profiles/{profile_id}/profileContactInfo"
        return self._make_request("GET", endpoint)

    def get_profile_top_card(self, linkedin_url: str) -> Dict:
        """Get detailed profile information using custom API.
        
        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username/")
        """
        profile_id = self.get_public_profile_id(linkedin_url)
        return self._make_request("POST", f"/profile/getTopCard?profile_id={profile_id}", use_custom_api=True)
    
    def get_profile_resume(self, linkedin_url: str) -> Dict:
        """Get detailed resume information using custom API.
        
        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username/")
            
        Returns:
            Dict: Resume data including experience, education, skills etc.
        """
        profile_id = self.get_public_profile_id(linkedin_url)
        return self._make_request("POST", f"/profile/getResume?profile_urn={profile_id}", use_custom_api=True)

    def get_profile_posts(
        self,
        linkedin_url: str,
        count: int = 1,
        limit: int = 10,
        until: dict = None,
        sleep: bool = True,
        pagination_token: str = None,
    ) -> pd.DataFrame:
        """Get posts feed for a LinkedIn profile.

        Args:
            linkedin_url (str): LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username/")
            count (int, optional): Number of posts per request. Defaults to 1. Max 100.
            limit (int, optional): Total number of posts to return. Defaults to 10. Use -1 for unlimited.
            until (dict, optional): Condition to stop fetching posts. Defaults to None.
            sleep (bool, optional): Whether to sleep between requests. Defaults to True.
            pagination_token (str, optional): Token for pagination. Defaults to None.

        Returns:
            pd.DataFrame: DataFrame containing posts data
        """
        TIME_SLEEP = 3  # Seconds between requests

        # Get profile ID if not provided
        profile_id = self.get_profile_id(linkedin_url)

        # Initialize until check
        until_check = False
        keys = list(until.keys()) if isinstance(until, dict) and until else []

        # Initialize loop variables
        start = 0
        df = pd.DataFrame()
        if limit != -1 and count > limit:
            limit = count

        while True:
            # Build request URL
            endpoint = f"/profile/getPostsFeed?profile_id={profile_id}&count={count}"
            if pagination_token:
                endpoint += f"&pagination_token={pagination_token}"

            # Make request
            response = self._make_request("POST", endpoint, use_custom_api=True)
            if not response:
                break

            # Convert to DataFrame
            tmp_df = pd.DataFrame(response)

            # Check until condition
            for key in keys:
                value = until.get(key)
                if key in tmp_df.columns and str(value) in tmp_df[key].astype(str).unique().tolist():
                    until_check = True
                    break

            # Get pagination token
            pagination_token = tmp_df.loc[0, "PAGINATION_TOKEN"] if not tmp_df.empty else None

            # Combine results
            df = pd.concat([df, tmp_df], axis=0)

            if until_check:
                break

            if sleep:
                time.sleep(TIME_SLEEP)

            start += count
            if limit != -1 and start >= limit:
                break

        return df.reset_index(drop=True)
    
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
            raise ValueError("URL must contain /company/, /school/ or /showcase/")
    
    def get_organization_details(self, linkedin_url: str) -> pd.DataFrame:
        """Get detailed information about a LinkedIn company.
        
        Args:
            linkedin_url (str, optional): LinkedIn organization URL. 

        Returns:
            pd.DataFrame: DataFrame containing company information
        """
        response = self._make_request("POST", f"/company/getInfo?company_url={self.get_organization_id(linkedin_url)}", use_custom_api=True)
        df = pd.DataFrame(response)
        return df.reset_index(drop=True)

    def get_organization_posts(
        self,
        linkedin_url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        sleep: bool = True,
    ) -> pd.DataFrame:
        """Get posts feed for a LinkedIn company.

        Args:
            linkedin_url (str): LinkedIn organization URL (e.g., "https://www.linkedin.com/company/naas-ai/")
            start (int, optional): Starting index for pagination. Defaults to 0.
            count (int, optional): Number of posts per request. Defaults to 100. Max 100.
            limit (int, optional): Total number of posts to return. Defaults to -1 (unlimited).
            sleep (bool, optional): Whether to sleep between requests. Defaults to True.

        Returns:
            pd.DataFrame: DataFrame containing company posts data with engagement metrics
        """
        TIME_SLEEP = 3  # Seconds between requests

        # Initialize loop variables
        df = pd.DataFrame()
        if limit != -1 and count > limit:
            count = limit

        while True:
            # Make request
            endpoint = f"/company/getPostsFeed?company_url={self.get_organization_id(linkedin_url)}&start={start}&count={count}"
            response = self._make_request("POST", endpoint, use_custom_api=True)
            
            if not response:
                break

            # Convert to DataFrame
            tmp_df = pd.DataFrame(response)

            # Combine results
            df = pd.concat([df, tmp_df], axis=0)

            if sleep:
                time.sleep(TIME_SLEEP)

            start += count
            if limit != -1 and start >= limit:
                break

        # Add engagement metrics if we have data
        if not df.empty:
            # Add views and calculate engagement score
            df["VIEWS"] = df["ACTIVITY_ID"].apply(self.get_post_views)
            df["ENGAGEMENT_SCORE"] = 0
            mask = df["VIEWS"] != 0
            df.loc[mask, "ENGAGEMENT_SCORE"] = (df.loc[mask, "COMMENTS"] + df.loc[mask, "LIKES"]) / df.loc[mask, "VIEWS"]

        return df.reset_index(drop=True)
    
    def get_activity_id(self, linkedin_url: str) -> str:
        """Extract activity ID from LinkedIn post URL."""
        if "-activity-" in linkedin_url:
            return linkedin_url.split("-activity-")[-1].split("-")[0]
        if ":activity:" in linkedin_url:
            return linkedin_url.split(":activity:")[-1].split("/")[0]
        return None

    def get_post_stats(self, linkedin_url: str) -> Dict:
        """Get post statistics using custom API.
        
        Args:
            linkedin_url (str): LinkedIn post URL (e.g., "https://www.linkedin.com/posts/username-activity-")
        """
        activity_id = self.get_activity_id(linkedin_url)
        return self._make_request("POST", f"/post/getStats?activity_id={activity_id}", use_custom_api=True)
    
    def get_post_views(self, activity_id: str) -> int:
        """Get view count for a specific post.

        Args:
            activity_id (str): LinkedIn activity ID

        Returns:
            int: Number of views for the post
        """
        views = 0
        req_url = f"{self.__configuration.base_url}/company/getPostsViews?activity_id={activity_id}"
        res = requests.post(req_url, cookies=self.cookies, headers=self.headers)
        res.raise_for_status()

        # Get result
        views = res.json().get("VIEWS")
        time.sleep(3)
        return views

    def get_post_comments(
        self, linkedin_url: str, start: int = 0, count: int = 100, limit: int = -1, sleep: bool = True
    ):
        """Get profiles who commented on a LinkedIn post.

        Args:
            linkedin_url (str): URL of the LinkedIn post to get comments from
            start (int, optional): Starting index for pagination. Defaults to 0.
            count (int, optional): Number of comments to retrieve per request. Defaults to 100.
            limit (int, optional): Maximum total number of comments to retrieve. Use -1 for no limit. Defaults to -1.
            sleep (bool, optional): Whether to sleep between requests to avoid rate limiting. Defaults to True.

        Returns:
            pd.DataFrame: DataFrame containing comment data with columns for commenter profiles
        """
        TIME_SLEEP = 3  # Seconds between requests
        
        # Get activity ID and validate
        activity_id = self.get_activity_id(linkedin_url)
        if not activity_id:
            logger.warning(f"Could not extract activity ID from URL: {linkedin_url}")
            return pd.DataFrame()
            
        logger.info(f"Activity ID: {activity_id}")

        df = pd.DataFrame()
        total_fetched = 0
        
        while True:
            # Adjust count if we're near the limit
            if limit != -1:
                remaining = limit - total_fetched
                if remaining <= 0:
                    break
                count = min(count, remaining)

            # Make request
            response = self._make_request(
                "POST",
                f"/post/getComments?activity_id={activity_id}&start={start}&count={count}",
                use_custom_api=True
            )

            # Break if no more results
            if not response or len(response) == 0:
                break

            # Convert to DataFrame and combine results
            tmp_df = pd.DataFrame(response)
            df = pd.concat([df, tmp_df], axis=0)
            
            # Update counters
            records_fetched = len(tmp_df)
            total_fetched += records_fetched
            start += records_fetched

            # Sleep between requests if needed
            if sleep:
                time.sleep(TIME_SLEEP)

            # Break if we got fewer records than requested (means we hit the end)
            if records_fetched < count:
                break

        return df.reset_index(drop=True)

    def get_post_reactions(
        self, linkedin_url: str, start: int = 0, count: int = 100, limit: int = -1, sleep: bool = True
    ):
        """Get profiles who liked a LinkedIn post.

        Args:
            linkedin_url (str): URL of the LinkedIn post to get likes from
            start (int, optional): Starting index for pagination. Defaults to 0.
            count (int, optional): Number of likes to retrieve per request. Defaults to 100.
            limit (int, optional): Maximum total number of likes to retrieve. Use -1 for no limit. Defaults to -1.
            sleep (bool, optional): Whether to sleep between requests to avoid rate limiting. Defaults to True.

        Returns:
            pd.DataFrame: DataFrame containing like data with columns for liker profiles
        """
        TIME_SLEEP = 3  # Seconds between requests
        
        # Get activity ID and validate
        activity_id = self.get_activity_id(linkedin_url)
        if not activity_id:
            logger.warning(f"Could not extract activity ID from URL: {linkedin_url}")
            return pd.DataFrame()

        df = pd.DataFrame()
        total_fetched = 0
        
        while True:
            # Adjust count if we're near the limit
            if limit != -1:
                remaining = limit - total_fetched
                if remaining <= 0:
                    break
                count = min(count, remaining)

            # Make request
            response = self._make_request(
                "POST",
                f"/post/getLikes?activity_id={activity_id}&start={start}&count={count}",
                use_custom_api=True
            )

            # Break if no more results
            if not response or len(response) == 0:
                break

            # Convert to DataFrame and combine results
            tmp_df = pd.DataFrame(response)
            df = pd.concat([df, tmp_df], axis=0)
            
            # Update counters
            records_fetched = len(tmp_df)
            total_fetched += records_fetched
            start += records_fetched

            # Sleep between requests if needed
            if sleep:
                time.sleep(TIME_SLEEP)

            # Break if we got fewer records than requested (means we hit the end)
            if records_fetched < count:
                break

        return df.reset_index(drop=True)

def as_tools(configuration: LinkedInIntegrationConfiguration):
    """Convert LinkedIn integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    
    integration = LinkedInIntegration(configuration)

    class GetProfileViewSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")

    class GetProfileNetworkSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")

    class GetProfileContactSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")

    class GetProfileTopCardSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")

    class GetProfileResumeSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")

    class GetOrganizationSchema(BaseModel):
        organization_url: str = Field(..., description="LinkedIn organization URL")

    class GetPostCommentsSchema(BaseModel):
        post_url: str = Field(..., description="LinkedIn post URL")
        limit: int = Field(default=1, description="Maximum number of comments to retrieve. Use -1 for no limit.")

    class GetPostReactionsSchema(BaseModel):
        post_url: str = Field(..., description="LinkedIn post URL")
        limit: int = Field(default=1, description="Maximum number of reactions to retrieve. Use -1 for no limit.")

    class GetProfilePostsSchema(BaseModel):
        profile_url: str = Field(..., description="LinkedIn profile URL")
        count: int = Field(default=1, description="Number of posts per request (max 100)")
        limit: int = Field(default=10, description="Total number of posts to return. Use -1 for unlimited.")
        until: Optional[Dict] = Field(default=None, description="Condition to stop fetching posts")
        pagination_token: Optional[str] = Field(default=None, description="Token for pagination")

    class GetOrganizationPostsSchema(BaseModel):
        organization_url: str = Field(..., description="LinkedIn organization URL")
        count: int = Field(default=100, description="Number of posts per request (max 100)")
        limit: int = Field(default=-1, description="Total number of posts to return. Use -1 for unlimited.")

    class GetPostStatsSchema(BaseModel):
        post_url: str = Field(..., description="LinkedIn post URL")

    return [
        StructuredTool(
            name="linkedin_get_profile_view",
            description="Get profile view information for a LinkedIn profile",
            func=lambda profile_url: integration.get_profile_view(profile_url),
            args_schema=GetProfileViewSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_network",
            description="Get network information for a LinkedIn profile",
            func=lambda profile_url: integration.get_profile_network(profile_url),
            args_schema=GetProfileNetworkSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_contact",
            description="Get contact information for a LinkedIn profile",
            func=lambda profile_url: integration.get_profile_contact(profile_url),
            args_schema=GetProfileContactSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_top_card",
            description="Get detailed profile information using custom API",
            func=lambda profile_url: integration.get_profile_top_card(profile_url),
            args_schema=GetProfileTopCardSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_resume",
            description="Get detailed resume information using custom API",
            func=lambda profile_url: integration.get_profile_resume(profile_url),
            args_schema=GetProfileResumeSchema
        ),
        StructuredTool(
            name="linkedin_get_organization", 
            description="Get details about a LinkedIn organization/company",
            func=lambda organization_url: integration.get_organization(organization_url),
            args_schema=GetOrganizationSchema
        ),
        StructuredTool(
            name="linkedin_get_post_comments",
            description="Get LinkedIn profiles who commented on a LinkedIn post",
            func=lambda post_url, limit: integration.get_post_comments(post_url, limit=limit),
            args_schema=GetPostCommentsSchema
        ),
        StructuredTool(
            name="linkedin_get_post_reactions",
            description="Get LinkedIn profiles who reacted on a LinkedIn post", 
            func=lambda post_url, limit: integration.get_post_reactions(post_url, limit=limit),
            args_schema=GetPostReactionsSchema
        ),
        StructuredTool(
            name="linkedin_get_profile_posts",
            description="Get posts feed for a LinkedIn profile",
            func=lambda profile_url, count=1, limit=10, until=None, pagination_token=None: 
                integration.get_profile_posts(profile_url, count=count, limit=limit, until=until, pagination_token=pagination_token),
            args_schema=GetProfilePostsSchema
        ),
        StructuredTool(
            name="linkedin_get_organization_posts",
            description="Get posts feed for a LinkedIn organization/company",
            func=lambda organization_url, count=100, limit=-1: 
                integration.get_organization_posts(organization_url, count=count, limit=limit),
            args_schema=GetOrganizationPostsSchema
        ),
        StructuredTool(
            name="linkedin_get_post_stats",
            description="Get statistics for a LinkedIn post",
            func=lambda post_url: integration.get_post_stats(post_url),
            args_schema=GetPostStatsSchema
        ),
    ]
