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
    name: str = "Cloudflare"
    description: str = "Cloudflare Workers AI for running foundation models at the edge with low latency."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/cloudflare.png"
    tags: list[str] = ['cloudflare', 'workers ai', 'edge']
    slug: str = "cloudflare"
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.cloudflare
        enabled: true
        config:
            cloudflare_api_key: "{{ secret.CLOUDFLARE_API_KEY }}"
            datastore_path: "cloudflare"
        """

        cloudflare_api_key: str
        datastore_path: str = "cloudflare"
