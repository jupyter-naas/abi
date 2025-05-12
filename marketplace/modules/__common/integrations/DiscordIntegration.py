from abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List
import requests

LOGO_URL = "https://logo.clearbit.com/discord.com"


@dataclass
class DiscordIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Discord integration.

    Attributes:
        bot_token (str): Discord Bot token for authentication
        base_url (str): Base URL for Discord API. Defaults to "https://discord.com/api/v10"
    """

    bot_token: str
    base_url: str = "https://discord.com/api/v10"


class DiscordIntegration(Integration):
    """Discord API integration client.

    This integration provides methods to interact with Discord's API endpoints.
    It handles authentication and request management.
    """

    __configuration: DiscordIntegrationConfiguration

    def __init__(self, configuration: DiscordIntegrationConfiguration):
        """Initialize Discord client with bot token."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bot {self.__configuration.bot_token}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self, method: str, endpoint: str, params: Dict = None, json: Dict = None
    ) -> Dict:
        """Make HTTP request to Discord API.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            params (Dict, optional): Query parameters. Defaults to None.
            json (Dict, optional): JSON body for POST requests. Defaults to None.

        Returns:
            Dict: Response JSON

        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, params=params, json=json
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Discord API request failed: {str(e)}")

    def get_guilds(self) -> List[Dict]:
        """Retrieve all guilds (servers) the bot has access to.

        Returns:
            List[Dict]: List of guild data

        Raises:
            IntegrationConnectionError: If the guilds retrieval fails
        """
        return self._make_request("GET", "/users/@me/guilds")

    def get_channels(self, guild_id: str) -> List[Dict]:
        """Retrieve all channels in a guild.

        Args:
            guild_id (str): The ID of the guild

        Returns:
            List[Dict]: List of channel data

        Raises:
            IntegrationConnectionError: If the channels retrieval fails
        """
        return self._make_request("GET", f"/guilds/{guild_id}/channels")

    def send_message(self, channel_id: str, content: str) -> Dict:
        """Send a message to a channel.

        Args:
            channel_id (str): The ID of the channel
            content (str): The message content

        Returns:
            Dict: Message data

        Raises:
            IntegrationConnectionError: If the message send fails
        """
        return self._make_request(
            "POST", f"/channels/{channel_id}/messages", json={"content": content}
        )


def as_tools(configuration: DiscordIntegrationConfiguration):
    """Convert Discord integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = DiscordIntegration(configuration)

    class GuildSchema(BaseModel):
        pass

    class ChannelSchema(BaseModel):
        guild_id: str = Field(..., description="Discord guild (server) ID")

    class MessageSchema(BaseModel):
        channel_id: str = Field(..., description="Discord channel ID")
        content: str = Field(..., description="Message content to send")

    return [
        StructuredTool(
            name="discord_get_guilds",
            description="Retrieve all guilds (servers) the bot has access to",
            func=lambda: integration.get_guilds(),
            args_schema=GuildSchema,
        ),
        StructuredTool(
            name="discord_get_channels",
            description="Retrieve all channels in a guild",
            func=lambda guild_id: integration.get_channels(guild_id),
            args_schema=ChannelSchema,
        ),
        StructuredTool(
            name="discord_send_message",
            description="Send a message to a Discord channel",
            func=lambda channel_id, content: integration.send_message(
                channel_id, content
            ),
            args_schema=MessageSchema,
        ),
    ]
