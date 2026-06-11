from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "Gemma"
    description: str = "Google's lightweight, open Gemma models for efficient language understanding and generation."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/gemma.png"
    tags: list[str] = ["google", "gemma", "open source"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.gemma
        enabled: true
        config:
            datastore_path: "gemma"
        """
        datastore_path: str = "gemma"
