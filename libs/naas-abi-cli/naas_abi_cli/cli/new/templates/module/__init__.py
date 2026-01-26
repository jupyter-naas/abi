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

    # on_initialized is called by the engine after all modules and services have been fully loaded.
    # At this point, you can safely access other modules and services through the engine's interfaces.
    # Override this method to implement any post-initialization logic your module requires.
    def on_initialized(self):
        super().on_initialized()

    # The on_load method is invoked during initial module loading by the engine.
    # At this point, avoid accessing services or other modules, as they have not been loaded yet.
    # Place any logic here that must occur right as the module is loaded, before initialization.
    # You can see it as the constructor of the module.
    def on_load(self):
        super().on_load()
