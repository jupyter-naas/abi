from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from abi.services.object_storage.ObjectStorageService import ObjectStorageService
from abi.services.secret.Secret import Secret
from abi.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["src.core.chatgpt", "src.core.templatablesparqlquery"],
        services=[Secret, TripleStoreService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        openai_api_key: str
