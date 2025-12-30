from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["naas_abi_marketplace.ai.chatgpt"],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.pubmed
        enabled: true
        config:
            datastore_path: "pubmed"
        """
        datastore_path: str = "pubmed"