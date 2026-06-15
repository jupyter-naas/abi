from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "Azure"
    description: str = "Microsoft Azure's cloud platform for deploying AI models and cognitive services."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/azure.png"
    tags: list[str] = ['microsoft', 'azure', 'cloud']
    slug: str = "azure"
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.azure
        enabled: true
        config:
            azure_api_key: "{{ secret.AZURE_API_KEY }}"
            datastore_path: "azure"
        """

        azure_api_key: str
        datastore_path: str = "azure"
