from naas_abi_core import logger
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
            datastore_path: "datastore/naas"
            naas_api_key: "{{ secret.NAAS_API_KEY }}"
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
        """
        datastore_path: str
        openai_api_key: str
        naas_api_key: str