from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any
from openai import OpenAI
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import os

LOGO_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/openai_100x100.png"

@dataclass
class OpenAIGpt4oIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAI GPT-4o integration.
    
    Attributes:
        api_key (str): OpenAI API key for authentication
    """
    api_key: str

class OpenAIGpt4oIntegration(Integration):
    """OpenAI GPT-4o integration class for interacting with OpenAI's API.
    
    This class provides methods specifically optimized for working with GPT-4o.
    It handles authentication, request management, and provides specialized methods
    for leveraging GPT-4o's capabilities.
    
    Attributes:
        __configuration (OpenAIGpt4oIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: OpenAIGpt4oIntegrationConfiguration

    def __init__(self, configuration: OpenAIGpt4oIntegrationConfiguration = None):
        """Initialize OpenAI client with configuration."""
        if configuration is None:
            # Default to environment variable if configuration not provided
            api_key = os.environ.get("OPENAI_API_KEY")
            configuration = OpenAIGpt4oIntegrationConfiguration(api_key=api_key)
            
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = OpenAI(api_key=self.__configuration.api_key)
        
    def create_chat_completion(
        self,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        messages: List[Dict[str, str]] = [],
        temperature: float = 0.3,
        response_format: Optional[Dict] = None,
        stream: bool = False,
        max_tokens: Optional[int] = None,
    ) -> Union[str, Any]:
        """Create a chat completion using GPT-4o.
        
        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with role and content
            prompt (Optional[str]): Prompt to use, defaults to None
            system_prompt (Optional[str]): System prompt to use, defaults to None
            temperature (float): Sampling temperature between 0 and 2, defaults to 0.3
            response_format (Optional[Dict]): Response format to use, defaults to None
            stream (bool): Whether to stream the response, defaults to False
            max_tokens (Optional[int]): Maximum number of tokens to generate, defaults to None
            
        Returns:
            Union[str, Any]: Completion text or streaming response
        """
        model = "gpt-4o"
        
        if messages == [] and prompt is not None:
            messages = []
            if system_prompt is not None:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
        
        params = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "stream": stream,
        }
        
        if response_format is not None:
            params["response_format"] = response_format
            
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
            
        completion = self.__client.chat.completions.create(**params)
        
        if stream:
            return completion
        
        return completion.choices[0].message.content
    
    def create_structured_output(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: BaseModel = None,
    ) -> Any:
        """Create a chat completion with structured output using GPT-4o.
        
        Args:
            prompt (str): Prompt to use
            system_prompt (Optional[str]): System prompt to use
            response_schema (BaseModel): Pydantic schema for the response format
            
        Returns:
            Any: Structured response according to the provided schema
        """
        messages = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        completion = self.__client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        content = completion.choices[0].message.content
        
        # If a schema is provided, parse the response
        if response_schema:
            try:
                import json
                json_content = json.loads(content)
                return response_schema.parse_obj(json_content)
            except Exception as e:
                return {"error": str(e), "content": content}
        
        return content
    
    def create_vision_analysis(
        self,
        prompt: str,
        image_urls: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """Analyze images using GPT-4o's vision capabilities.
        
        Args:
            prompt (str): Prompt describing what to analyze in the images
            image_urls (List[str]): List of image URLs to analyze
            system_prompt (Optional[str]): System prompt to use
            temperature (float): Sampling temperature between 0 and 2, defaults to 0.3
            
        Returns:
            str: Analysis of the images
        """
        messages = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
            
        # Construct the message content with text and images
        content = [{"type": "text", "text": prompt}]
        
        # Add each image as content
        for image_url in image_urls:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
            
        messages.append({"role": "user", "content": content})
        
        completion = self.__client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=temperature
        )
        
        return completion.choices[0].message.content


def as_tools(configuration: OpenAIGpt4oIntegrationConfiguration = None):
    """Convert GPT-4o integration into LangChain tools."""
    integration = OpenAIGpt4oIntegration(configuration)

    class CreateChatCompletionSchema(BaseModel):
        prompt: str = Field(description="The prompt to use")
        system_prompt: Optional[str] = Field(None, description="The system prompt to use")
        temperature: Optional[float] = Field(0.3, description="The temperature to use")
        response_format: Optional[Dict] = Field(None, description="The response format to use")
        max_tokens: Optional[int] = Field(None, description="Maximum number of tokens to generate")

    class CreateStructuredOutputSchema(BaseModel):
        prompt: str = Field(description="The prompt to use")
        system_prompt: Optional[str] = Field(None, description="The system prompt to use")
        response_schema: Optional[BaseModel] = Field(None, description="Pydantic schema for the response format")

    class CreateVisionAnalysisSchema(BaseModel):
        prompt: str = Field(description="Prompt describing what to analyze in the images")
        image_urls: List[str] = Field(description="List of image URLs to analyze")
        system_prompt: Optional[str] = Field(None, description="The system prompt to use")
        temperature: Optional[float] = Field(0.3, description="The temperature to use")

    return [
        StructuredTool(
            name="gpt4o_chat_completion",
            description="Create a chat completion using GPT-4o",
            func=lambda **kwargs: integration.create_chat_completion(**kwargs),
            args_schema=CreateChatCompletionSchema
        ),
        StructuredTool(
            name="gpt4o_structured_output",
            description="Create a structured JSON output using GPT-4o",
            func=lambda **kwargs: integration.create_structured_output(**kwargs),
            args_schema=CreateStructuredOutputSchema
        ),
        StructuredTool(
            name="gpt4o_vision_analysis",
            description="Analyze images using GPT-4o's vision capabilities",
            func=lambda **kwargs: integration.create_vision_analysis(**kwargs),
            args_schema=CreateVisionAnalysisSchema
        ),
    ] 