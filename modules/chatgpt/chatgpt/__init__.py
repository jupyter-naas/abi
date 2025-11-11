from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from abi.services.secret.Secret import Secret


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[Secret])

    class Configuration(ModuleConfiguration):
        openai_api_key: str
