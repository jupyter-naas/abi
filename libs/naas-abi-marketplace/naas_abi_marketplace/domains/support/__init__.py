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
            "naas_abi_marketplace.applications.github",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.domains.support
        enabled: true
        config:
            datastore_path: "datastore/support"
            github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"
            default_repository: "jupyter-naas/abi"
            github_project_id: 12
            project_node_id: "PVT_kwDOBESWNM4AKRt3"
            iteration_field_id: "PVTIF_lADOBESWNM4AKRt3zgGZRc4"
            status_field_id: "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
            status_option_id: "97363483"
            priority_field_id: "PVTSSF_lADOBESWNM4AKRt3zgGac0g"
            priority_option_id: "4fb76f2d"
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
        """
        datastore_path: str
        github_access_token: str
        default_repository: str
        github_project_id: int
        openai_api_key: str
        project_node_id: str
        iteration_field_id: str
        status_field_id: str
        status_option_id: str
        priority_field_id: str
        priority_option_id: str