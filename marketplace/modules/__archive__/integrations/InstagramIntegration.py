from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict, List

LOGO_URL = "https://logo.clearbit.com/instagram.com"


@dataclass
class InstagramIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Instagram integration.

    Attributes:
        access_token (str): Instagram API access token
        base_url (str): Base URL for Instagram Graph API
        version (str): Version of the Instagram API
    """

    access_token: str
    base_url: str = "https://graph.instagram.com"
    version: str = "v21.0"


class InstagramIntegration(Integration):
    """Instagram integration for accessing Instagram Graph API.

    This class provides methods to interact with Instagram's Graph API endpoints.
    It handles authentication and request management.

    Attributes:
        __configuration (InstagramIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.

    Example:
        >>> config = InstagramIntegrationConfiguration(
        ...     access_token="your_access_token"
        ... )
        >>> integration = InstagramIntegration(config)
    """

    __configuration: InstagramIntegrationConfiguration

    def __init__(self, configuration: InstagramIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_user_profile(self) -> Dict:
        """Get the authenticated user's profile information.

        Returns:
            Dict: User profile data including id, username, etc.
        """
        params = {
            "access_token": self.__configuration.access_token,
            "fields": "id,username,account_type,media_count",
        }
        response = requests.get(f"{self.__configuration.base_url}/me", params=params)
        response.raise_for_status()
        return response.json()

    def get_media(self, limit: int = 25) -> List[Dict]:
        """Get the user's media posts.

        Args:
            limit (int): Maximum number of media items to return. Defaults to 25.

        Returns:
            List[Dict]: List of media items with their details
        """
        params = {
            "access_token": self.__configuration.access_token,
            "fields": "id,caption,media_type,media_url,permalink,timestamp",
            "limit": limit,
        }
        response = requests.get(
            f"{self.__configuration.base_url}/me/media", params=params
        )
        response.raise_for_status()
        return response.json()["data"]

    def get_media_insights(self, media_id: str) -> Dict:
        """Get insights/metrics for a specific media item.

        Args:
            media_id (str): ID of the media item

        Returns:
            Dict: Engagement metrics for the media item
        """
        params = {
            "access_token": self.__configuration.access_token,
            "metric": "engagement,impressions,reach",
        }
        response = requests.get(
            f"{self.__configuration.base_url}/{media_id}/insights", params=params
        )
        response.raise_for_status()
        return response.json()

    def send_message(self, to: str, message: str) -> Dict:
        """Send a direct message to a specified Instagram user.

        Args:
            to (str): Instagram username of the recipient
            message (str): Text message to send

        Returns:
            Dict: Response from the Instagram API containing message details
        """
        headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Content-Type": "application/json",
        }

        payload = {"recipient": {"username": to}, "message": {"text": message}}

        response = requests.post(
            f"{self.__configuration.base_url}/{self.__configuration.version}/me/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def as_tools(configuration: InstagramIntegrationConfiguration):
    """Convert Instagram integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = InstagramIntegration(configuration)

    class GetUserProfileSchema(BaseModel):
        pass

    class GetMediaSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of media items to return")

    class GetMediaInsightsSchema(BaseModel):
        media_id: str = Field(
            ..., description="ID of the media item to get insights for"
        )

    class SendMessageSchema(BaseModel):
        to: str = Field(..., description="Instagram username of the recipient")
        message: str = Field(..., description="Text message to send")

    return [
        StructuredTool(
            name="instagram_get_profile",
            description="Get the authenticated user's Instagram profile information",
            func=lambda: integration.get_user_profile(),
            args_schema=GetUserProfileSchema,
        ),
        StructuredTool(
            name="instagram_get_media",
            description="Get the user's Instagram media posts",
            func=lambda limit: integration.get_media(limit),
            args_schema=GetMediaSchema,
        ),
        StructuredTool(
            name="instagram_get_media_insights",
            description="Get insights/metrics for a specific Instagram media item",
            func=lambda media_id: integration.get_media_insights(media_id),
            args_schema=GetMediaInsightsSchema,
        ),
        StructuredTool(
            name="instagram_send_message",
            description="Send a direct message to a specified Instagram user",
            func=lambda to, message: integration.send_message(to, message),
            args_schema=SendMessageSchema,
        ),
    ]
