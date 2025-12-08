from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        gemini_api_key: str
