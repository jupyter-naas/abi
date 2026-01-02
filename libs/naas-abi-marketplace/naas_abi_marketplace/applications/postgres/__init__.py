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

        module: naas_abi_marketplace.applications.postgres
        enabled: true
        config:
            postgres_user: "{{ secret.POSTGRES_USER }}"
            postgres_password: "{{ secret.POSTGRES_PASSWORD }}"
            postgres_dbname: "{{ secret.POSTGRES_DBNAME }}"
            postgres_host: "{{ secret.POSTGRES_HOST }}"
            postgres_port: "{{ secret.POSTGRES_PORT }}"
        """

        postgres_user: str
        postgres_password: str
        postgres_dbname: str
        postgres_host: str
        postgres_port: str
        datastore_path: str = "postgres"
