from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class ABIModule(BaseModule):
    name: str = "Zettafox"
    description: str = "Zettafox AI agent powered by Qwen models for customized conversational AI."
    logo_url: str = "naas_abi_marketplace/ai/zettafox/assets/public/zettafox-logo-square.png"
    tags: list[str] = ["zettafox", "custom", "language model"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.zettafox
        enabled: true
        config:
            qwen_litellm_auth_header: "{{ secret.QWEN_LITELLM_AUTH_HEADER }}"
        """

        qwen_litellm_auth_header: str
