from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class _Configuration(ModuleConfiguration):
    """
    Configuration example:

    module: naas_abi_marketplace.applications.linkedin
    enabled: true
    config:
        li_at: "{{ secret.li_at }}"
        JSESSIONID: "{{ secret.JSESSIONID }}"
        linkedin_profile_url: "https://www.linkedin.com/in/your-profile-id/"
    """
    li_at: str
    JSESSIONID: str
    linkedin_profile_url: str
    datastore_path: str = "linkedin"


class ABIModule(BaseModule[_Configuration]):
    Configuration = _Configuration
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_marketplace.applications.google_search",
            "naas_abi_marketplace.applications.naas",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )
