
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from pydantic import BaseModel, ConfigDict


class ModelRegistryServiceConfiguration(BaseModel):
    """Configuration for the in-memory ModelRegistry.

    Example::

      model_registry:
        default_chat_model: "gpt-5.1-mini"
        default_embedding_model: "text-embedding-3-small"
    """

    model_config = ConfigDict(extra="forbid")

    default_chat_model: str | None = None
    default_embedding_model: str | None = None

    def load(self) -> ModelRegistryService:
        return ModelRegistryService(
            default_chat_model=self.default_chat_model,
            default_embedding_model=self.default_embedding_model,
        )
