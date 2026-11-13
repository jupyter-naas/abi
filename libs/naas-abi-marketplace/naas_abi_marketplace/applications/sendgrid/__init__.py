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

        module: naas_abi_marketplace.applications.sendgrid
        enabled: true
        config:
            sendgrid_api_key: "{{ secret.SENDGRID_API_KEY }}"
            sendgrid_allowed_senders: ["support@example.com"]
        """
        sendgrid_api_key: str
        datastore_path: str = "sendgrid"
        # The only addresses the agent sends mail from; none by default.
        sendgrid_allowed_senders: list[str] = []
