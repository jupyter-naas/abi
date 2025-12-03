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
        datastore_path: "linkedin"
        li_at: "{{ secret.li_at }}"
        JSESSIONID: "{{ secret.JSESSIONID }}"
        linkedin_profile_url: "https://www.linkedin.com/in/your-profile-id/"
        openai_api_key: "{{ secret.OPENAI_API_KEY }}"
        google_custom_search_api_key: "{{ secret.GOOGLE_CUSTOM_SEARCH_API_KEY }}"
        google_custom_search_engine_id: "{{ secret.GOOGLE_CUSTOM_SEARCH_ENGINE_ID }}"
    """

    datastore_path: str
    li_at: str
    JSESSIONID: str
    linkedin_profile_url: str
    openai_api_key: str
    google_custom_search_api_key: str
    google_custom_search_engine_id: str


class ABIModule(BaseModule[_Configuration]):
    Configuration = _Configuration
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_marketplace.applications.google_search#soft",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )
