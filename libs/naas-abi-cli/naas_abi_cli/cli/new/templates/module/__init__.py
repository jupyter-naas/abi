from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

# from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
# from naas_abi_core.services.secret.Secret import Secret
# from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
# from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
        ],
        services=[
            # Secret,
            # TripleStoreService,
            # ObjectStorageService,
            # VectorStoreService
        ],
    )

    class Configuration(ModuleConfiguration):
        pass
        # example: str

    def on_initialized(self):
        super().on_initialized()
