from typing import Optional, Dict, List, Any, Union
import requests
import asyncio
import websockets
import json
import time
from dataclasses import dataclass
from pydantic import BaseModel, Field
from abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration

@dataclass
class GladiaIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Gladia integration.
    
    Attributes:
        api_key (str): Gladia API key for authentication
        base_url (str): Base URL for Gladia API
        enable_diarization (bool): Enable speaker diarization
        enable_sentiment_analysis (bool): Enable sentiment analysis
        enable_named_entity_recognition (bool): Enable named entity recognition
        enable_summarization (bool): Enable automatic summarization
        language_preference (str): Preferred language for transcription
        custom_vocabulary (List[str]): Custom vocabulary terms
        model_type (str): Model to use ('solaria' or 'whisper-zero')
    """
    api_key: str
    base_url: str = "https://api.gladia.io"
    enable_diarization: bool = False
    enable_sentiment_analysis: bool = False
    enable_named_entity_recognition: bool = False
    enable_summarization: bool = False
    language_preference: str = "auto"
    custom_vocabulary: List[str] = None
    model_type: str = "solaria"

class TranscriptionJob(BaseModel):
    """Represents a Gladia transcription job."""
    job_id: str = Field(description="Unique job identifier")
    status: str = Field(description="Job status: queued, processing, done, error")
    result_url: Optional[str] = Field(description="URL to fetch results", default=None)
    created_at: str = Field(description="Job creation timestamp")
    audio_url: Optional[str] = Field(description="Source audio URL", default=None)
    audio_duration: Optional[float] = Field(description="Audio duration in seconds", default=None)

class Speaker(BaseModel):
    """Represents a speaker in transcription."""
    speaker_id: str = Field(description="Unique speaker identifier")
    name: Optional[str] = Field(description="Speaker name if known", default=None)
    segments: List[Dict] = Field(description="Speaker segments with timing")

class TranscriptionResult(BaseModel):
    """Represents transcription results with metadata."""
    full_transcript: str = Field(description="Complete transcription text")
    confidence: float = Field(description="Overall confidence score")
    language: str = Field(description="Detected language")
    speakers: Optional[List[Speaker]] = Field(description="Speaker information", default=None)
    sentiment_analysis: Optional[Dict] = Field(description="Sentiment analysis results", default=None)
    named_entities: Optional[List[Dict]] = Field(description="Named entities found", default=None)
    summary: Optional[str] = Field(description="Automatic summary", default=None)
    word_timestamps: List[Dict] = Field(description="Word-level timestamps")
    processing_time: float = Field(description="Processing time in seconds")

class GladiaIntegration(Integration):
    """Gladia Speech-to-Text API integration client.
    
    This integration provides methods to interact with Gladia's speech-to-text API endpoints
    for both real-time and asynchronous transcription with advanced audio intelligence features.
    """

    __configuration: GladiaIntegrationConfiguration

    def __init__(self, configuration: GladiaIntegrationConfiguration):
        """Initialize Gladia client with API key and configuration."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        if not self.__configuration.custom_vocabulary:
            self.__configuration.custom_vocabulary = []
        
        self.headers = {
            "x-gladia-key": self.__configuration.api_key,
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, timeout: int = 120) -> Dict:
        """Make HTTP request to Gladia API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Gladia API request failed: {str(e)}")

    def transcribe_audio_async(
        self, 
        audio_url: str,
        language: Optional[str] = None,
        enable_diarization: Optional[bool] = None,
        enable_sentiment_analysis: Optional[bool] = None,
        enable_named_entity_recognition: Optional[bool] = None,
        enable_summarization: Optional[bool] = None,
        custom_vocabulary: Optional[List[str]] = None
    ) -> TranscriptionJob:
        """Submit audio for asynchronous transcription.
        
        Args:
            audio_url: URL of the audio file to transcribe
            language: Language code (overrides configuration)
            enable_diarization: Enable speaker diarization (overrides configuration)
            enable_sentiment_analysis: Enable sentiment analysis (overrides configuration)
            enable_named_entity_recognition: Enable NER (overrides configuration)
            enable_summarization: Enable summarization (overrides configuration)
            custom_vocabulary: Custom vocabulary terms (overrides configuration)
            
        Returns:
            TranscriptionJob object with job details
        """
        # Use configuration defaults if parameters not provided
        config = self.__configuration
        request_data = {
            "audio_url": audio_url,
            "diarization": enable_diarization if enable_diarization is not None else config.enable_diarization,
            "translation": False  # Keep simple for now
        }
        
        # Add language if not auto-detect
        if language and language != "auto":
            request_data["language"] = language
        elif config.language_preference != "auto":
            request_data["language"] = config.language_preference
            
        # Add optional features based on configuration
        if enable_sentiment_analysis if enable_sentiment_analysis is not None else config.enable_sentiment_analysis:
            request_data["sentiment_analysis"] = True
            
        if enable_named_entity_recognition if enable_named_entity_recognition is not None else config.enable_named_entity_recognition:
            request_data["named_entity_recognition"] = True
            
        if enable_summarization if enable_summarization is not None else config.enable_summarization:
            request_data["summarization"] = True

        try:
            response = self._make_request("POST", "/v2/transcription/", request_data)
            

            return TranscriptionJob(
                job_id=response.get("id", response.get("request_id", "unknown")),
                status=response.get("status", "submitted"),
                result_url=response.get("result_url"),
                created_at=response.get("created_at", ""),
                audio_url=audio_url
            )
        except KeyError as e:
            raise IntegrationConnectionError(f"Failed to submit transcription job: Missing field {str(e)} in response: {response}")
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to submit transcription job: {str(e)}")

    def get_transcription_status(self, job_id: str) -> TranscriptionJob:
        """Get the status of a transcription job.
        
        Args:
            job_id: The transcription job ID
            
        Returns:
            TranscriptionJob object with current status
        """
        try:
            response = self._make_request("GET", f"/v2/transcription/{job_id}")
            
            return TranscriptionJob(
                job_id=job_id,
                status=response["status"],
                result_url=response.get("result_url"),
                created_at=response.get("created_at", ""),
                audio_duration=response.get("audio_duration")
            )
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get transcription status: {str(e)}")

    def get_transcription_result(self, result_url: str) -> TranscriptionResult:
        """Retrieve transcription results from result URL.
        
        Args:
            result_url: URL to fetch transcription results
            
        Returns:
            TranscriptionResult object with complete results
        """
        try:
            # Remove base URL if present in result_url
            if result_url.startswith(self.__configuration.base_url):
                endpoint = result_url[len(self.__configuration.base_url):]
            else:
                endpoint = result_url
                
            response = self._make_request("GET", endpoint)
            
            if response["status"] != "done":
                raise IntegrationConnectionError(f"Transcription not complete. Status: {response['status']}")
            
            result_data = response["result"]
            transcription_data = result_data["transcription"]
            
            # Extract speakers if diarization is enabled
            speakers = None
            if "speakers" in result_data:
                speakers = [
                    Speaker(
                        speaker_id=speaker["speaker"],
                        name=speaker.get("name"),
                        segments=speaker.get("segments", [])
                    )
                    for speaker in result_data["speakers"]
                ]
            
            return TranscriptionResult(
                full_transcript=transcription_data["full_transcript"],
                confidence=transcription_data.get("confidence", 0.0),
                language=result_data.get("language", self.__configuration.language_preference),
                speakers=speakers,
                sentiment_analysis=result_data.get("sentiment_analysis"),
                named_entities=result_data.get("named_entities"),
                summary=result_data.get("summary"),
                word_timestamps=transcription_data.get("words", []),
                processing_time=result_data.get("processing_time", 0.0)
            )
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get transcription result: {str(e)}")






