from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, BinaryIO
import requests

LOGO_URL = "https://logo.clearbit.com/gladia.io"


@dataclass
class GladiaIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Gladia integration.

    Attributes:
        api_key (str): Gladia API key for authentication
        base_url (str): Base URL for Gladia API. Defaults to "https://api.gladia.io"
    """

    api_key: str
    base_url: str = "https://api.gladia.io"


class GladiaIntegration(Integration):
    """Gladia API integration client.

    This integration provides methods to interact with Gladia's API endpoints
    for audio transcription and text-to-speech services.
    """

    __configuration: GladiaIntegrationConfiguration

    def __init__(self, configuration: GladiaIntegrationConfiguration):
        """Initialize Gladia client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "x-gladia-key": self.__configuration.api_key,
            "Accept": "application/json",
        }

    def _make_request(
        self, endpoint: str, method: str = "POST", files: Dict = None, json: Dict = None
    ) -> Dict:
        """Make HTTP request to Gladia API.

        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (POST, GET, etc.). Defaults to "POST"
            files (Dict, optional): Files to upload. Defaults to None.
            json (Dict, optional): JSON body for requests. Defaults to None.

        Returns:
            Dict: Response JSON

        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, files=files, json=json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Gladia API request failed: {str(e)}")

    def transcribe_audio(
        self,
        audio_file: BinaryIO,
        language_to: str = "auto",
        toggle_diarization: bool = False,
        toggle_direct_translate: bool = False,
    ) -> Dict:
        """Transcribe audio file to text.

        Args:
            audio_file (BinaryIO): Audio file to transcribe
            language_to (str, optional): Target language. Defaults to "auto".
            toggle_diarization (bool, optional): Enable speaker diarization. Defaults to False.
            toggle_direct_translate (bool, optional): Enable direct translation. Defaults to False.

        Returns:
            Dict: Transcription result

        Raises:
            IntegrationConnectionError: If the transcription fails
        """
        files = {"audio": audio_file}

        data = {
            "language_to": language_to,
            "toggle_diarization": toggle_diarization,
            "toggle_direct_translate": toggle_direct_translate,
        }

        return self._make_request("/audio/text/transcribe", files=files, json=data)

    def text_to_speech(
        self,
        text: str,
        voice_id: str = "default",
        language: str = "en",
        audio_format: str = "mp3",
    ) -> bytes:
        """Convert text to speech.

        Args:
            text (str): Text to convert to speech
            voice_id (str, optional): Voice ID to use. Defaults to "default".
            language (str, optional): Language code. Defaults to "en".
            audio_format (str, optional): Output audio format. Defaults to "mp3".

        Returns:
            bytes: Audio data

        Raises:
            IntegrationConnectionError: If the text-to-speech conversion fails
        """
        payload = {
            "text": text,
            "voice_id": voice_id,
            "language": language,
            "audio_format": audio_format,
        }

        return self._make_request("/text/audio/tts", json=payload)

    def list_available_voices(self) -> List[Dict]:
        """Get list of available voices for text-to-speech.

        Returns:
            List[Dict]: List of available voices and their properties

        Raises:
            IntegrationConnectionError: If the voice listing fails
        """
        return self._make_request("/text/audio/voices", method="GET")


def as_tools(configuration: GladiaIntegrationConfiguration):
    """Convert Gladia integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GladiaIntegration(configuration)

    class TranscriptionSchema(BaseModel):
        audio_path: str = Field(..., description="Path to audio file to transcribe")
        language_to: str = Field(
            default="auto", description="Target language for transcription"
        )
        toggle_diarization: bool = Field(
            default=False, description="Enable speaker diarization"
        )
        toggle_direct_translate: bool = Field(
            default=False, description="Enable direct translation"
        )

    class TTSSchema(BaseModel):
        text: str = Field(..., description="Text to convert to speech")
        voice_id: str = Field(default="default", description="Voice ID to use")
        language: str = Field(default="en", description="Language code")
        audio_format: str = Field(default="mp3", description="Output audio format")

    class VoiceListSchema(BaseModel):
        pass

    def transcribe_wrapper(**kwargs):
        with open(kwargs["audio_path"], "rb") as audio_file:
            return integration.transcribe_audio(
                audio_file,
                kwargs["language_to"],
                kwargs["toggle_diarization"],
                kwargs["toggle_direct_translate"],
            )

    return [
        StructuredTool(
            name="gladia_transcribe_audio",
            description="Transcribe audio file to text",
            func=transcribe_wrapper,
            args_schema=TranscriptionSchema,
        ),
        StructuredTool(
            name="gladia_text_to_speech",
            description="Convert text to speech",
            func=lambda text,
            voice_id,
            language,
            audio_format: integration.text_to_speech(
                text, voice_id, language, audio_format
            ),
            args_schema=TTSSchema,
        ),
        StructuredTool(
            name="gladia_list_voices",
            description="Get list of available voices for text-to-speech",
            func=lambda: integration.list_available_voices(),
            args_schema=VoiceListSchema,
        ),
    ]
