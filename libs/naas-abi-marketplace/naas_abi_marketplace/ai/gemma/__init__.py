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
    logo_url: str = "https://cdn.jsdelivr.net/npm/@lobehub/icons-static-png@2.10.0/dark/gemma-color.png"
    tags: list[str] = ["google", "gemma", "open source"]
    slug: str = "gemma"
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
