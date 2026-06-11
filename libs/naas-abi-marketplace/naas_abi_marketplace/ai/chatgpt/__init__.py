from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from naas_abi_core.models.Model import ModelProvider
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "ChatGPT"
    description: str = "OpenAI's ChatGPT for web search, image analysis, and general-purpose AI assistance."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
    tags: list[str] = ["openai", "chatgpt", "language model"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, ModelRegistryService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.chatgpt
        enabled: true
        config:
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
            openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
        """
        openai_api_key: str
        openrouter_api_key: str | None = None
        datastore_path: str = "chatgpt"

    def on_load(self):
        # BaseModule.on_load auto-discovers every models/*.py file that
        # exposes CANONICAL_ID + model and registers them.
        super().on_load()

        # Register the openai chat factory for off-catalog model ids.
        api_key = SecretStr(self.configuration.openai_api_key)

        def openai_chat_factory(provider_model_id: str) -> ChatOpenAI:
            return ChatOpenAI(
                model=provider_model_id,
                temperature=0,
                timeout=120,
                max_retries=3,
                api_key=api_key,
            )

        self.engine.services.model_registry.register_chat_provider(
            ModelProvider.OPENAI, openai_chat_factory
        )

        def openai_embedding_factory(provider_model_id: str) -> OpenAIEmbeddings:
            return OpenAIEmbeddings(model=provider_model_id, api_key=api_key)

        self.engine.services.model_registry.register_embedding_provider(
            ModelProvider.OPENAI, openai_embedding_factory
        )
