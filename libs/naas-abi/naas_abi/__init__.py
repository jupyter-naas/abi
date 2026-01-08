from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_marketplace.ai.qwen#soft",
            "naas_abi_marketplace.applications.github#soft",
            "naas_abi_marketplace.applications.naas#soft",
            "naas_abi_marketplace.domains.support#soft",
        ],
        services=[Secret, TripleStoreService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi
        enabled: true
        config:
            datastore_path: "abi"
            workspace_id: "{{ secret.WORKSPACE_ID }}"
            storage_name: "{{ secret.STORAGE_NAME }}"
        """

        datastore_path: str = "abi"
        workspace_id: str | None = None
        storage_name: str | None = None

    # def on_initialized(self):
    #     if (
    #         self.configuration.anthropic_api_key is not None
    #         and "naas_abi_marketplace.ai.claude" not in self.engine.modules
    #     ):
    #         raise ValueError(
    #             "anthropic_api_key is provided but naas_abi_marketplace.ai.claude is not available"
    #         )
