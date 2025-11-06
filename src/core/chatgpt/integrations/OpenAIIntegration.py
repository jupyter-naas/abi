from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Dict, List, Optional
from openai import OpenAI
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from abi.services.cache.CacheFactory import CacheFactory
from abi.services.cache.CachePort import DataType
from datetime import timedelta

cache = CacheFactory.CacheFS_find_storage(subpath="openai")

@dataclass
class OpenAIIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAI integration.
    
    Attributes:
        api_key (str): OpenAI API key for authentication
    """
    api_key: str

class OpenAIIntegration(Integration):
    """OpenAI integration class for interacting with OpenAI's API.
    
    This class provides methods to interact with OpenAI's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (OpenAIIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: OpenAIIntegrationConfiguration

    def __init__(self, configuration: OpenAIIntegrationConfiguration):
        """Initialize OpenAI client with configuration."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = OpenAI(api_key=self.__configuration.api_key)
        
    def list_models(self) -> Dict:
        """List available models."""
        models_page = self.__client.models.list()
        return {"models": [model.model_dump() for model in models_page.data]}
    
    @cache(lambda self, model_id: f"retrieve_model_{model_id}", cache_type=DataType.PICKLE, ttl=timedelta(days=1))
    def retrieve_model(self, model_id: str) -> Dict:
        """Retrieve a specific model."""
        model = self.__client.models.retrieve(model_id)
        return model.model_dump()

    def create_chat_completion(
        self,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        messages: List[Dict[str, str]] = [],
        model: Optional[str] = "o3-mini",
        temperature: float = 0.3,
        response_format: Optional[str] = None,
    ) -> Optional[str]:
        """Create a chat completion using OpenAI's API.
        
        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with role and content
            prompt (Optional[str]): Prompt to use, defaults to None
            system_prompt (Optional[str]): System prompt to use, defaults to None
            model (Optional[str]): Model ID to use, defaults to gpt-4o
            temperature (float): Sampling temperature between 0 and 2, defaults to 0.7
            response_format (Optional[str]): Response format to use, defaults to None
            
        Returns:
            Dict: API response containing the completion
        """
        if not messages and prompt is not None and system_prompt is not None:
            messages = [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        
        # Ensure model is not None
        if model is None:
            model = "o3-mini"
            
        # Create completion with proper error handling
        if model.startswith("o"):
            completion = self.__client.chat.completions.create(
                messages=messages,  # type: ignore
                model=model,
            )
        else:
            completion = self.__client.chat.completions.create(
                messages=messages,  # type: ignore
                model=model,
                temperature=temperature,
            )
        return completion.choices[0].message.content
    
    def create_chat_completion_beta(
        self,
        prompt: str,
        system_prompt: str,
        model: str = "o3-mini",
        response_format: Optional[BaseModel] = None,
    ) -> Optional[str]:
        """Create a chat completion beta with structured output using OpenAI's API.
        
        Args:
            prompt (str): Prompt to use
            system_prompt (str): System prompt to use
            model (str): Model ID to use, defaults to gpt-4o
            response_format (BaseModel): Response format to use
            
        Returns:
            Dict: API response containing the completion
        """
        messages = [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        completion = self.__client.beta.chat.completions.parse(
            messages=messages,  # type: ignore
            model=model,
            response_format=response_format,  # type: ignore
        )
        return completion.choices[0].message.content
    

def as_tools(configuration: OpenAIIntegrationConfiguration):
    """Convert OpenAI integration into LangChain tools."""
    integration = OpenAIIntegration(configuration)

    class ListModelsSchema(BaseModel):
        pass

    class RetrieveModelSchema(BaseModel):
        model_id: str = Field(description="The ID of the model to retrieve")

    class CreateChatCompletionSchema(BaseModel):
        prompt: str = Field(description="The prompt to use")
        system_prompt: str = Field(description="The system prompt to use")
        model: str = Field(description="The model to use")
        temperature: float = Field(description="The temperature to use")
        response_format: str = Field(description="The response format to use")

    class CreateChatCompletionBetaSchema(BaseModel):
        prompt: str = Field(description="The prompt to use")
        system_prompt: str = Field(description="The system prompt to use")
        model: str = Field(description="The model to use")
        response_format: Optional[BaseModel] = Field(description="The response format to use")

    return [
        StructuredTool(
            name="openai_list_models",
            description="List available OpenAI models",
            func=lambda **kwargs: integration.list_models(**kwargs),
            args_schema=ListModelsSchema
        ),
        StructuredTool(
            name="openai_retrieve_model",
            description="Retrieve a specific OpenAI model",
            func=lambda **kwargs: integration.retrieve_model(**kwargs),
            args_schema=RetrieveModelSchema
        ),
        StructuredTool(
            name="openai_create_chat_completion",
            description="Create a chat completion using OpenAI's API",
            func=lambda **kwargs: integration.create_chat_completion(**kwargs),
            args_schema=CreateChatCompletionSchema
        ),
        StructuredTool(
            name="openai_create_chat_completion_beta",
            description="Create a chat completion beta using OpenAI's API.",
            func=lambda **kwargs: integration.create_chat_completion_beta(**kwargs),
            args_schema=CreateChatCompletionBetaSchema
        ),
    ]