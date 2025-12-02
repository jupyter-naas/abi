from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.github
        enabled: true
        config:
            datastore_path: "datastore/support"
            github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
        """
        datastore_path: str
        github_access_token: str
        openai_api_key: str