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
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.mistral
        enabled: true
        config:
            mistral_api_key: "{{ secret.MISTRAL_API_KEY }}"
        """
        mistral_api_key: str
        datastore_path: str = "mistral"
