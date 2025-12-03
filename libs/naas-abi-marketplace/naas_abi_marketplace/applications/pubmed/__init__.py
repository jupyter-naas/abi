from naas_abi_core.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies

class _Configuration(ModuleConfiguration):
    pass

class ABIModule(BaseModule[_Configuration]):
    Configuration = _Configuration
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["naas_abi_marketplace.ai.chatgpt"],
        services=[],
    )