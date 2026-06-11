from langchain_anthropic import ChatAnthropic
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
    name: str = "Claude"
    description: str = "Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png"
    tags: list[str] = ["anthropic", "claude", "language model"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, ModelRegistryService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.claude
        enabled: true
        config:
            anthropic_api_key: "{{ secret.ANTHROPIC_API_KEY }}"
        """
        anthropic_api_key: str
        datastore_path: str = "claude"

    def on_load(self):
        # BaseModule.on_load auto-discovers and registers every model file
        # under ``models/*.py`` that exposes CANONICAL_ID + model.
        super().on_load()

        # We only need to register the generic provider factory used for
        # off-catalog ids (model ids the module doesn't ship a concrete file
        # for).
        api_key = SecretStr(self.configuration.anthropic_api_key)

        def anthropic_chat_factory(provider_model_id: str) -> ChatAnthropic:
            return ChatAnthropic(
                model_name=provider_model_id,
                temperature=0,
                max_retries=2,
                api_key=api_key,
                timeout=None,
                stop=None,
            )

        self.engine.services.model_registry.register_chat_provider(
            ModelProvider.ANTHROPIC, anthropic_chat_factory
        )
