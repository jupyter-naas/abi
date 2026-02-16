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

        module: naas_abi_marketplace.applications.algolia
        enabled: true
        config:
            algolia_api_key: "{{ secret.ALGOLIA_API_KEY }}"
            algolia_application_id: "{{ secret.ALGOLIA_APPLICATION_ID }}"
        """

        algolia_api_key: str
        algolia_application_id: str
        datastore_path: str = "algolia"
