
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class ModelRegistryFactory:
    @staticmethod
    def InMemory(
        default_chat_model: str | None = None,
        default_embedding_model: str | None = None,
    ) -> ModelRegistryService:
        return ModelRegistryService(
            default_chat_model=default_chat_model,
            default_embedding_model=default_embedding_model,
        )
