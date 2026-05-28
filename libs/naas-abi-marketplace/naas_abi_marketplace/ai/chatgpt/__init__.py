import os

from langchain_openai import ChatOpenAI
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

    def on_initialized(self):
        super().on_initialized()
        # We setup the OPENAI_API_KEY environment variable as OpenAI SDK requires it. Also, the IntentMapper will fallback to using OpenAI so it need to be in the environment.
        os.environ["OPENAI_API_KEY"] = self.configuration.openai_api_key
