from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
        ],
        services=[TripleStoreService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.naas
        enabled: true
        config:
            naas_api_key: "{{ secret.NAAS_API_KEY }}"
            workspace_id: "{{ secret.WORKSPACE_ID }}"
            storage_name: "{{ secret.STORAGE_NAME }}"
        """
        naas_api_key: str
        workspace_id: str | None = None
        storage_name: str | None = None
        datastore_path: str = "naas"
