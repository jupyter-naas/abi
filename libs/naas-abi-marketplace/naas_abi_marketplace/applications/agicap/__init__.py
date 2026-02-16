from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["naas_abi_marketplace.ai.chatgpt"],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.agicap
        enabled: true
        config:
            agicap_username: "{{ secret.AGICAP_USERNAME }}"
            agicap_password: "{{ secret.AGICAP_PASSWORD }}"
            agicap_client_id: "{{ secret.AGICAP_CLIENT_ID }}"
            agicap_client_secret: "{{ secret.AGICAP_CLIENT_SECRET }}"
            agicap_bearer_token: "{{ secret.AGICAP_BEARER_TOKEN }}"
            agicap_api_token: "{{ secret.AGICAP_API_TOKEN }}"
        """

        agicap_username: str
        agicap_password: str
        agicap_client_id: str
        agicap_client_secret: str
        agicap_bearer_token: str
        agicap_api_token: str
        datastore_path: str = "agicap"
