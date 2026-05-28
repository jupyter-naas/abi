from typing import Optional

from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class ModelRegistryFactory:
    @staticmethod
    def InMemory(
        default_chat_model: Optional[str] = None,
        default_embedding_model: Optional[str] = None,
        default_provider: Optional[str] = None,
    ) -> ModelRegistryService:
        return ModelRegistryService(
            default_chat_model=default_chat_model,
            default_embedding_model=default_embedding_model,
            default_provider=default_provider,
        )
