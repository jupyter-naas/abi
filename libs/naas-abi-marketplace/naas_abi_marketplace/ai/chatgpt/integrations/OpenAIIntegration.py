import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional

from langchain_core.tools import StructuredTool
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.StorageUtils import StorageUtils
from openai import OpenAI
from pydantic import BaseModel, Field

cache = CacheFactory.CacheFS_find_storage(subpath="openai")


@dataclass
class OpenAIIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAI integration.

    Attributes:
        api_key (str): OpenAI API key for authentication
        datastore_path (str): Path to the datastore
        object_storage (ObjectStorageService): Object storage service
    """

    api_key: str
    datastore_path: str
    object_storage: ObjectStorageService


class OpenAIIntegration(Integration):
    """OpenAI integration class for interacting with OpenAI's API.

    This class provides methods to interact with OpenAI's API endpoints.
    It handles authentication and request management.

    Attributes:
        __configuration (OpenAIIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: OpenAIIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: OpenAIIntegrationConfiguration):
        """Initialize OpenAI client with configuration."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__openai = OpenAI(api_key=self.__configuration.api_key)
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    @cache(
        lambda self: "list_models", cache_type=DataType.PICKLE, ttl=timedelta(days=1)
    )
    def list_models(self) -> Dict:
        """List available models."""
        models = self.__openai.models.list()
        output_dir = os.path.join(self.__configuration.datastore_path, "models", "_all")
        data = [model.model_dump() for model in models.data]
        self.__storage_utils.save_json(data, output_dir, "models.json")
        return {"models": data}

    @cache(
        lambda self, model_id: f"retrieve_model_{model_id}",
        cache_type=DataType.PICKLE,
        ttl=timedelta(days=1),
    )
    def retrieve_model(self, model_id: str) -> Dict:
        """Retrieve a specific model."""
        model = self.__openai.models.retrieve(model_id)
        output_dir = os.path.join(
            self.__configuration.datastore_path, "models", model_id
        )
        self.__storage_utils.save_json(
            model.model_dump(), output_dir, f"{model_id}_info.json"
        )
        return model.model_dump()

    @cache(
        lambda self,
        prompt,
        system_prompt,
        messages,
        model,
        temperature: f"{prompt}_{system_prompt}_{messages}_{model}_{temperature}",
        cache_type=DataType.PICKLE,
        ttl=timedelta(days=1),
    )
    def create_chat_completion(
        self,
        prompt: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        messages: List[Dict[str, str]] = [],
        model: str = "o3-mini",
        temperature: float = 0.3,
    ) -> Dict:
        """Create a chat completion using OpenAI's API.

        Args:
            prompt (Optional[str]): Prompt to use, defaults to None
            system_prompt (str): System prompt to use, defaults to "You are a helpful assistant."
            messages (List[Dict[str, str]]): List of message dictionaries with role and content
            model (Optional[str]): Model ID to use, defaults to o3-mini
            temperature (float): Sampling temperature between 0 and 2, defaults to 0.3

        Returns:
            Dict: API response containing the completion
        """
        if not messages and prompt is not None and system_prompt is not None:
            messages = [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

        # Create completion with proper error handling
        if model.startswith("o"):
            completion = self.__openai.chat.completions.create(
                messages=messages,  # type: ignore
                model=model,
            )
        else:
            completion = self.__openai.chat.completions.create(
                messages=messages,  # type: ignore
                model=model,
                temperature=temperature,
            )
        if (
            hasattr(completion, "choices")
            and len(completion.choices) > 0
            and hasattr(completion.choices[0], "message")
            and hasattr(completion.choices[0].message, "content")
        ):
            output_dir = os.path.join(
                self.__configuration.datastore_path, "completions", model
            )
            self.__storage_utils.save_json(
                dict(completion), output_dir, f"{model}_{temperature}.json"
            )
            content = completion.choices[0].message.content
            return {"content": content}
        return {}


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

    return [
        StructuredTool(
            name="openai_list_models",
            description="List available OpenAI models",
            func=lambda **kwargs: integration.list_models(**kwargs),
            args_schema=ListModelsSchema,
        ),
        StructuredTool(
            name="openai_retrieve_model",
            description="Retrieve a specific OpenAI model",
            func=lambda **kwargs: integration.retrieve_model(**kwargs),
            args_schema=RetrieveModelSchema,
        ),
        StructuredTool(
            name="openai_create_chat_completion",
            description="Create a chat completion using OpenAI's API",
            func=lambda **kwargs: integration.create_chat_completion(**kwargs),
            args_schema=CreateChatCompletionSchema,
        ),
    ]
