from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        pass
