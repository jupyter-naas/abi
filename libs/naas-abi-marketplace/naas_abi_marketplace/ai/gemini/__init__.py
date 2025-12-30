from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[ObjectStorageService])

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.gemini
        enabled: true
        config:
            gemini_api_key: "{{ secret.GEMINI_API_KEY }}"
        """
        gemini_api_key: str
        datastore_path: str = "gemini"
        
