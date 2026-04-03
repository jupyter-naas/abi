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

        module: naas_abi_marketplace.applications.sec_gov
        enabled: true
        config:
            user_agent: "NAAS-ABI-Marketplace/1.0 (florent@naas.ai)"
            datastore_path: "sec_gov"
        """

        user_agent: str
        datastore_path: str = "sec_gov"
