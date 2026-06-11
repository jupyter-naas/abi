from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "DeepSeek"
    description: str = "DeepSeek's open-source models for advanced reasoning, mathematics, and problem-solving."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/deepseek.png"
    tags: list[str] = ["deepseek", "reasoning", "open source"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.deepseek
        enabled: true
        config:
            datastore_path: "deepseek"
        """
        datastore_path: str = "deepseek"
