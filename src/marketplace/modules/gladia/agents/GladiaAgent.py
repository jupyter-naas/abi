from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from abi import logger
from src.marketplace.modules.gladia.models.solaria import model
from typing import Optional
from enum import Enum

NAME = "Gladia"
DESCRIPTION = "AI agent for speech-to-text transcription using Gladia's advanced models with support for real-time and batch processing."
AVATAR_URL = "https://assets-global.website-files.com/64b43dcce44f4a76d6e1c5b4/64b43dcce44f4a76d6e1c676_favicon.png"
SYSTEM_PROMPT = """# ROLE
You are Gladia, an AI agent for speech-to-text transcription using Gladia's API.

# CORE CAPABILITIES
- Transcribe YouTube videos and audio files
- Check transcription status and retrieve results
- Launch CLI transcription tool

# TOOLS
- transcribe_youtube_video: Transcribe YouTube videos
- get_transcription_status: Check job status and get results
- open_cli_app: Launch CLI transcription tool

# CONSTRAINTS
- Requires GLADIA_API_KEY for functionality
"""

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    # Check if model is available
    if model is None:
        logger.error("Gladia agent not available - missing OpenAI API key")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
    
    tools: list = []

    # Create actual Gladia tools (not from intentmapping since they don't exist there)
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Optional
    
    class YouTubeTranscribeInput(BaseModel):
        video_url: str = Field(description="YouTube video URL to transcribe")
        language: Optional[str] = Field(default="auto", description="Language code or 'auto' for detection")
    
    class EmptyInput(BaseModel):
        pass
    
    class TranscriptionStatusInput(BaseModel):
        job_id: str = Field(description="The transcription job ID to check status for")
    
    def transcribe_youtube_video(video_url: str, language: str = "auto") -> dict:
        """Transcribe audio from a YouTube video URL."""
        import os
        from src import secret
        
        # Check for Gladia API key
        gladia_api_key = secret.get("GLADIA_API_KEY")
        
        if not gladia_api_key:
            return {
                "status": "demo_mode",
                "message": f"Demo: Would transcribe YouTube video {video_url} in language {language}",
                "video_url": video_url,
                "language": language,
                "note": "Set GLADIA_API_KEY environment variable for actual transcription"
            }
        
        # If we have an API key, use the GladiaIntegration
        try:
            from ..integrations.GladiaIntegration import (
                GladiaIntegration, GladiaIntegrationConfiguration
            )
            
            config = GladiaIntegrationConfiguration(api_key=gladia_api_key)
            integration = GladiaIntegration(configuration=config)
            
            # Start async transcription for YouTube video
            job = integration.transcribe_audio_async(
                audio_url=video_url,
                language=language if language != "auto" else None,
                enable_diarization=True,
                enable_sentiment_analysis=True
            )
            
            return {
                "status": "processing",
                "message": f"Transcription started for YouTube video {video_url}",
                "video_url": video_url,
                "language": language,
                "job_id": job.job_id,
                "result_url": job.result_url,
                "note": "Transcription in progress. Use get_transcription_status to check status."
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to start transcription: {str(e)}",
                "video_url": video_url,
                "error": str(e)
            }
    
    def open_cli_app() -> dict:
        """Open the CLI transcription tool."""
        import subprocess
        import os
        
        try:
            cmd = ["python", "src/marketplace/modules/gladia/apps/cli/playground.py"]
            subprocess.Popen(cmd, cwd="/Users/jrvmac/abi")
            return {
                "status": "launched",
                "message": "CLI transcription tool launched",
                "command": "python src/marketplace/modules/gladia/apps/cli/playground.py"
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to launch CLI: {str(e)}"}
    
    def get_transcription_status(job_id: str) -> dict:
        """Get the status of a transcription job."""
        from src import secret
        
        gladia_api_key = secret.get("GLADIA_API_KEY")
        if not gladia_api_key:
            return {
                "status": "error",
                "message": "GLADIA_API_KEY not found in environment"
            }
        
        try:
            from ..integrations.GladiaIntegration import (
                GladiaIntegration, GladiaIntegrationConfiguration
            )
            
            config = GladiaIntegrationConfiguration(api_key=gladia_api_key)
            integration = GladiaIntegration(configuration=config)
            
            status = integration.get_transcription_status(job_id)
            
            if status.status == "done" and status.result_url:
                result = integration.get_transcription_result(status.result_url)
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "transcription": result.full_transcript,
                    "confidence": result.confidence,
                    "language": result.language,
                    "speakers": len(result.speakers) if result.speakers else 0,
                    "processing_time": result.processing_time
                }
            else:
                result = {
                    "job_id": job_id,
                    "status": status.status,
                    "result_url": status.result_url,
                    "audio_duration": status.audio_duration
                }
            
            return {
                "status": "success",
                "job_id": job_id,
                "result": result
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get transcription status: {str(e)}",
                "job_id": job_id,
                "error": str(e)
            }
    
    # Add tools
    tools.extend([
        StructuredTool(
            name="transcribe_youtube_video",
            description="Transcribe audio from a YouTube video URL",
            func=transcribe_youtube_video,
            args_schema=YouTubeTranscribeInput
        ),
        StructuredTool(
            name="get_transcription_status",
            description="Get the status and result of a transcription job",
            func=get_transcription_status,
            args_schema=TranscriptionStatusInput
        ),
        StructuredTool(
            name="open_cli_app",
            description="Launch the CLI transcription tool",
            func=lambda: open_cli_app(),
            args_schema=EmptyInput
        )
    ])
    
    # Define agents
    agents: list = []

    # Define intents (simplified to avoid OpenAI API key requirement)
    intents: list = []
    
    return GladiaAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools, 
        agents=agents,
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class GladiaAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME, 
        name: str = NAME.replace("_", " "), 
        description: str = "API endpoints to call the Gladia agent completion.", 
        description_stream: str = "API endpoints to call the Gladia agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
