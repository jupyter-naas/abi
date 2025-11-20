from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from abi.services.secret.Secret import Secret
from abi.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[], services=[Secret, TripleStoreService]
    )

    class Configuration(ModuleConfiguration):
        openai_api_key: str


def requirements():
    return True
