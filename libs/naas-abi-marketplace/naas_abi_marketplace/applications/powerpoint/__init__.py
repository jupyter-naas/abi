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
            "naas_abi_marketplace.applications.naas",
        ],
        services=[TripleStoreService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.powerpoint
        enabled: true
        config:
            datastore_path: "datastore/powerpoint"
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
            naas_api_key: "{{ secret.NAAS_API_KEY }}"
            workspace_id: "{{ config.workspace_id }}"
            storage_name: "{{ config.storage_name }}"
        """

        datastore_path: str
        openai_api_key: str
        naas_api_key: str
        workspace_id: str
        storage_name: str
