from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

LOGO_URL = "https://logo.clearbit.com/youtube.com"

@dataclass
class YouTubeIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YouTube integration.
    
    Attributes:
        api_key (str): YouTube Data API key for authentication
        api_version (str): YouTube Data API version. Defaults to "v3"
    """
    api_key: str
    api_version: str = "v3"

class YouTubeIntegration(Integration):
    """YouTube API integration client.
    
    This class provides methods to interact with YouTube's Data API endpoints.
    """

    __configuration: YouTubeIntegrationConfiguration
    __youtube: any  # YouTube API client

    def __init__(self, configuration: YouTubeIntegrationConfiguration):
        """Initialize YouTube client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__youtube = build(
            'youtube', 
            self.__configuration.api_version, 
            developerKey=self.__configuration.api_key
        )

    def search_videos(self, 
                     query: str, 
                     max_results: int = 10, 
                     order: str = "relevance") -> List[Dict]:
        """Search for YouTube videos.
        
        Args:
            query (str): Search query
            max_results (int, optional): Maximum number of results. Defaults to 10.
            order (str, optional): Order of results. Defaults to "relevance".
            
        Returns:
            List[Dict]: List of video data
            
        Raises:
            IntegrationConnectionError: If the search fails
        """
        try:
            request = self.__youtube.search().list(
                q=query,
                part="snippet",
                maxResults=max_results,
                order=order,
                type="video"
            )
            response = request.execute()
            return response.get('items', [])
        except HttpError as e:
            raise IntegrationConnectionError(f"YouTube API request failed: {str(e)}")

    def get_video_details(self, video_id: str) -> Dict:
        """Get detailed information about a specific video.
        
        Args:
            video_id (str): YouTube video ID
            
        Returns:
            Dict: Video details
            
        Raises:
            IntegrationConnectionError: If the video details retrieval fails
        """
        try:
            request = self.__youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id
            )
            response = request.execute()
            items = response.get('items', [])
            return items[0] if items else {}
        except HttpError as e:
            raise IntegrationConnectionError(f"YouTube API request failed: {str(e)}")

    def get_channel_info(self, channel_id: str) -> Dict:
        """Get information about a YouTube channel.
        
        Args:
            channel_id (str): YouTube channel ID
            
        Returns:
            Dict: Channel information
            
        Raises:
            IntegrationConnectionError: If the channel info retrieval fails
        """
        try:
            request = self.__youtube.channels().list(
                part="snippet,contentDetails,statistics",
                id=channel_id
            )
            response = request.execute()
            items = response.get('items', [])
            return items[0] if items else {}
        except HttpError as e:
            raise IntegrationConnectionError(f"YouTube API request failed: {str(e)}")

    def get_video_comments(self, 
                          video_id: str, 
                          max_results: int = 100) -> List[Dict]:
        """Get comments for a specific video.
        
        Args:
            video_id (str): YouTube video ID
            max_results (int, optional): Maximum number of comments. Defaults to 100.
            
        Returns:
            List[Dict]: List of comments
            
        Raises:
            IntegrationConnectionError: If the comments retrieval fails
        """
        try:
            request = self.__youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=max_results
            )
            response = request.execute()
            return response.get('items', [])
        except HttpError as e:
            raise IntegrationConnectionError(f"YouTube API request failed: {str(e)}")

def as_tools(configuration: YouTubeIntegrationConfiguration):
    """Convert YouTube integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = YouTubeIntegration(configuration)
    
    class SearchSchema(BaseModel):
        query: str = Field(..., description="Search query for videos")
        max_results: int = Field(default=10, description="Maximum number of results to return")
        order: str = Field(
            default="relevance",
            description="Order of results (relevance, date, rating, title, viewCount)"
        )

    class VideoSchema(BaseModel):
        video_id: str = Field(..., description="YouTube video ID")

    class ChannelSchema(BaseModel):
        channel_id: str = Field(..., description="YouTube channel ID")

    class CommentsSchema(BaseModel):
        video_id: str = Field(..., description="YouTube video ID")
        max_results: int = Field(default=100, description="Maximum number of comments to return")
    
    return [
        StructuredTool(
            name="search_youtube_videos",
            description="Search for YouTube videos",
            func=lambda query, max_results, order: integration.search_videos(query, max_results, order),
            args_schema=SearchSchema
        ),
        StructuredTool(
            name="get_youtube_video_details",
            description="Get detailed information about a specific video",
            func=lambda video_id: integration.get_video_details(video_id),
            args_schema=VideoSchema
        ),
        StructuredTool(
            name="get_youtube_channel_info",
            description="Get information about a YouTube channel",
            func=lambda channel_id: integration.get_channel_info(channel_id),
            args_schema=ChannelSchema
        ),
        StructuredTool(
            name="get_youtube_video_comments",
            description="Get comments for a specific video",
            func=lambda video_id, max_results: integration.get_video_comments(video_id, max_results),
            args_schema=CommentsSchema
        )
    ] 