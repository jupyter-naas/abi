from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "Llama"
    description: str = "Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/llama.jpeg"
    tags: list[str] = ["meta", "llama", "open source"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.llama
        enabled: true
        config:
            datastore_path: "llama"
        """
        datastore_path: str = "llama"
