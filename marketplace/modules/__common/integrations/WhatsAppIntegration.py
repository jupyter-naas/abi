from abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict

LOGO_URL = "https://logo.clearbit.com/whatsapp.com"


@dataclass
class WhatsAppIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for WhatsApp integration.

    Attributes:
        access_token (str): WhatsApp API access token
        phone_number_id (str): WhatsApp Business Account phone number ID
        base_url (str): Base URL for WhatsApp Cloud API
        version (str): WhatsApp Cloud API version
    """

    access_token: str
    phone_number_id: str
    base_url: str = "https://graph.facebook.com"
    version: str = "v21.0"


class WhatsAppIntegration(Integration):
    """WhatsApp integration for accessing WhatsApp Cloud API.

    This class provides methods to interact with WhatsApp's Cloud API endpoints.
    It handles authentication and request management.

    Attributes:
        __configuration (WhatsAppIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.

    Example:
        >>> config = WhatsAppIntegrationConfiguration(
        ...     access_token="your_access_token",
        ...     phone_number_id="your_phone_number_id",
        ...     version="v21.0"
        ... )
        >>> integration = WhatsAppIntegration(config)
    """

    __configuration: WhatsAppIntegrationConfiguration

    def __init__(self, configuration: WhatsAppIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def send_message(self, to: str, message: str) -> Dict:
        """Send a WhatsApp message to a specified number.

        Args:
            to (str): Recipient's phone number in international format
            message (str): Text message to send

        Returns:
            Dict: Response from the WhatsApp API containing message details
        """
        headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }

        response = requests.post(
            f"{self.__configuration.base_url}/{self.__configuration.version}/{self.__configuration.phone_number_id}/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def as_tools(configuration: WhatsAppIntegrationConfiguration):
    """Convert WhatsApp integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = WhatsAppIntegration(configuration)

    class SendMessageSchema(BaseModel):
        to: str = Field(
            ..., description="Recipient's phone number in international format"
        )
        message: str = Field(..., description="Text message to send")

    return [
        StructuredTool(
            name="whatsapp_send_message",
            description="Send a WhatsApp message to a specified number.",
            func=lambda to, message: integration.send_message(to, message),
            args_schema=SendMessageSchema,
        )
    ]
