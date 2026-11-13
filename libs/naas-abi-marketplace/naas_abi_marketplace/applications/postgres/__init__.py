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
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.postgres
        enabled: true
        config:
            postgres_user: "{{ secret.POSTGRES_INTEGRATION_USER }}"
            postgres_password: "{{ secret.POSTGRES_INTEGRATION_PASSWORD }}"
            postgres_dbname: "{{ secret.POSTGRES_INTEGRATION_DBNAME }}"
            postgres_host: "{{ secret.POSTGRES_INTEGRATION_HOST }}"
            postgres_port: "{{ secret.POSTGRES_INTEGRATION_PORT }}"

        Everyone who may use the Postgres agent acts with this role: give it a
        database and a role of their own, never the platform's database, and a
        role that may only read. Queries run one statement at a time in a
        read-only transaction unless ``postgres_read_only`` is false.
        """

        postgres_user: str
        postgres_password: str
        postgres_dbname: str
        postgres_host: str
        postgres_port: str
        datastore_path: str = "postgres"
        postgres_read_only: bool = True
