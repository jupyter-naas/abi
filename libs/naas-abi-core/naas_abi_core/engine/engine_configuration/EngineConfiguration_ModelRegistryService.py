from typing import Optional

from pydantic import BaseModel, ConfigDict

from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class ModelRegistryServiceConfiguration(BaseModel):
    """Configuration for the in-memory ModelRegistry.

    Example::

      model_registry:
        default_chat_model: "gpt-5.1-mini"
        default_embedding_model: "text-embedding-3-small"
        default_provider: "openai"
    """

    model_config = ConfigDict(extra="forbid")

    default_chat_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_provider: Optional[str] = None

    def load(self) -> ModelRegistryService:
        return ModelRegistryService(
            default_chat_model=self.default_chat_model,
            default_embedding_model=self.default_embedding_model,
            default_provider=self.default_provider,
        )
