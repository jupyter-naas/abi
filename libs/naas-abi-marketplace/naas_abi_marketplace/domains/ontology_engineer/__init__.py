from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
        ],
        services=[ObjectStorageService, TripleStoreService, VectorStoreService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.domains.support
        enabled: true
        config:
            datastore_path: "ontology-engineer"
        """

        datastore_path: str = "ontology-engineer"
