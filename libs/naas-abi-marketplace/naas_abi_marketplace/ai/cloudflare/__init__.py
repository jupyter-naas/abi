from typing import Optional

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
    privacy_policy_url: str = "https://developers.cloudflare.com/workers-ai/privacy"
    terms_of_service_url: str = "https://www.cloudflare.com/service-specific-terms-developer-platform/#developer-platform-terms"
    status_page_url: Optional[str] = 'https://www.cloudflarestatus.com/'
    headquarters: str = "US"
    datacenters: Optional[list] = None

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
