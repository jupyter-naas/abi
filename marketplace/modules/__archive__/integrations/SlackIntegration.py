from abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests

LOGO_URL = "https://logo.clearbit.com/slack.com"


@dataclass
class SlackIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Slack integration.

    Attributes:
        bot_token (str): Slack Bot User OAuth Token for authentication
        base_url (str): Base URL for Slack API. Defaults to "https://slack.com/api"

    Note that this integration requires a Slack Bot User OAuth Token with appropriate scopes such as:
        channels:read
        users:read
        chat:write
        groups:read
        im:read
        mpim:read
    """

    bot_token: str
    base_url: str = "https://slack.com/api"


class SlackIntegration(Integration):
    """Slack API integration client.

    This integration provides methods to interact with Slack's API endpoints.
    It handles authentication and request management.
    """

    __configuration: SlackIntegrationConfiguration

    def __init__(self, configuration: SlackIntegrationConfiguration):
        """Initialize Slack client with bot token."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.bot_token}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self, endpoint: str, method: str = "GET", params: Dict = None, json: Dict = None
    ) -> Dict:
        """Make HTTP request to Slack API.

        Args:
            endpoint (str): API endpoint (e.g., 'chat.postMessage')
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            params (Dict, optional): Query parameters. Defaults to None.
            json (Dict, optional): JSON body for POST requests. Defaults to None.

        Returns:
            Dict: Response JSON

        Raises:
            IntegrationConnectionError: If request fails or Slack returns an error
        """
        url = f"{self.__configuration.base_url}/{endpoint}"

        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, params=params, json=json
            )
            response.raise_for_status()
            data = response.json()

            # Slack API always returns 200 but includes 'ok' field to indicate success
            if not data.get("ok", False):
                raise IntegrationConnectionError(
                    f"Slack API error: {data.get('error', 'Unknown error')}"
                )

            return data

        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Slack API request failed: {str(e)}")

    def list_channels(
        self, types: str = "public_channel,private_channel"
    ) -> List[Dict]:
        """Retrieve all channels the bot has access to.

        Args:
            types (str, optional): Comma-separated list of channel types.
                Defaults to "public_channel,private_channel"

        Returns:
            List[Dict]: List of channel data

        Raises:
            IntegrationConnectionError: If the channels retrieval fails
        """
        response = self._make_request(
            "conversations.list", method="GET", params={"types": types}
        )
        return response.get("channels", [])

    def list_users(self) -> List[Dict]:
        """Retrieve all users in the workspace.

        Returns:
            List[Dict]: List of user data

        Raises:
            IntegrationConnectionError: If the users retrieval fails
        """
        response = self._make_request("users.list", method="GET")
        return response.get("members", [])

    def send_message(
        self, channel: str, text: str, thread_ts: Optional[str] = None
    ) -> Dict:
        """Send a message to a channel.

        Args:
            channel (str): Channel ID or name
            text (str): Message text
            thread_ts (str, optional): Thread timestamp to reply to. Defaults to None.

        Returns:
            Dict: Message data

        Raises:
            IntegrationConnectionError: If the message send fails
        """
        payload = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts

        return self._make_request("chat.postMessage", method="POST", json=payload)

    def get_channel_history(self, channel: str, limit: int = 100) -> List[Dict]:
        """Retrieve message history from a channel.

        Args:
            channel (str): Channel ID
            limit (int, optional): Maximum number of messages to return. Defaults to 100.

        Returns:
            List[Dict]: List of message data

        Raises:
            IntegrationConnectionError: If the history retrieval fails
        """
        response = self._make_request(
            "conversations.history",
            method="GET",
            params={"channel": channel, "limit": limit},
        )
        return response.get("messages", [])


def as_tools(configuration: SlackIntegrationConfiguration):
    """Convert Slack integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = SlackIntegration(configuration)

    class ChannelListSchema(BaseModel):
        types: str = Field(
            default="public_channel,private_channel",
            description="Comma-separated list of channel types to include",
        )

    class UserListSchema(BaseModel):
        pass

    class MessageSchema(BaseModel):
        channel: str = Field(..., description="Channel ID or name to send message to")
        text: str = Field(..., description="Message text to send")
        thread_ts: Optional[str] = Field(
            None, description="Thread timestamp to reply to"
        )

    class HistorySchema(BaseModel):
        channel: str = Field(..., description="Channel ID to get history from")
        limit: int = Field(
            default=100, description="Maximum number of messages to return"
        )

    return [
        StructuredTool(
            name="slack_list_channels",
            description="Retrieve all channels the bot has access to in Slack.",
            func=lambda types: integration.list_channels(types),
            args_schema=ChannelListSchema,
        ),
        StructuredTool(
            name="slack_list_users",
            description="Retrieve all users in the workspace in Slack.",
            func=lambda: integration.list_users(),
            args_schema=UserListSchema,
        ),
        StructuredTool(
            name="slack_send_message",
            description="Send a message to a Slack channel.",
            func=lambda channel, text, thread_ts: integration.send_message(
                channel, text, thread_ts
            ),
            args_schema=MessageSchema,
        ),
        StructuredTool(
            name="slack_get_channel_history",
            description="Retrieve message history from a Slack channel.",
            func=lambda channel, limit: integration.get_channel_history(channel, limit),
            args_schema=HistorySchema,
        ),
    ]
