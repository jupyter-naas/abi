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
            "naas_abi_marketplace.ai.gemini",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.google_search
        enabled: true
        config:
            datastore_path: "datastore/google_search"
            google_custom_search_api_key: "{{ secret.GOOGLE_CUSTOM_SEARCH_API_KEY }}"
            google_custom_search_engine_id: "{{ secret.GOOGLE_CUSTOM_SEARCH_ENGINE_ID }}"
        """
        datastore_path: str
        google_custom_search_api_key: str
        google_custom_search_engine_id: str
