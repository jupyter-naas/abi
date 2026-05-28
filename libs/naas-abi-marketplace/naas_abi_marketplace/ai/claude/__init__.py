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
        super().on_load()

        registry = self.engine.services.model_registry
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

        registry.register_chat_provider(ModelProvider.ANTHROPIC, anthropic_chat_factory)

        # Eagerly importing the model modules triggers ChatModel construction
        # at the top of each file (which in turn requires ``ABIModule.get_instance()``
        # to have been called — guaranteed since we are inside on_load, after __init__).
        from naas_abi_marketplace.ai.claude.models import (
            claude_haiku_4_5,
            claude_opus_4,
            claude_opus_4_1,
            claude_sonnet_3_7,
            claude_sonnet_4,
            claude_sonnet_4_5,
        )

        for module in (
            claude_haiku_4_5,
            claude_opus_4,
            claude_opus_4_1,
            claude_sonnet_3_7,
            claude_sonnet_4,
            claude_sonnet_4_5,
        ):
            registry.register(module.CANONICAL_ID, module.model)
