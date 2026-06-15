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
    logo_url: str = "https://media.licdn.com/dms/image/v2/C510BAQEVMulA_Z8bWA/company-logo_200_200/company-logo_200_200/0/1631316626589?e=2147483647&v=beta&t=ekfwsqf39kkGnNHf4J-yGlgzD4zfYI7jjsRdg6nrovU"
    tags: list[str] = ["zettafox", "custom", "language model"]
    slug: str = "zettafox"
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
