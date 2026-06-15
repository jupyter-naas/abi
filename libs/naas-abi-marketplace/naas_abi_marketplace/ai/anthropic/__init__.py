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
    name: str = "Anthropic"
    description: str = "Anthropic's AI safety company providing Claude models for safe and beneficial AI."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png"
    tags: list[str] = ['anthropic', 'claude', 'language model']
    slug: str = "anthropic"
    privacy_policy_url: str = "https://www.anthropic.com/legal/privacy"
    terms_of_service_url: str = "https://www.anthropic.com/legal/commercial-terms"
    status_page_url: Optional[str] = 'https://status.anthropic.com/'
    headquarters: str = "US"
    datacenters: Optional[list] = None

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.anthropic
        enabled: true
        config:
            anthropic_api_key: "{{ secret.ANTHROPIC_API_KEY }}"
            datastore_path: "anthropic"
        """

        anthropic_api_key: str
        datastore_path: str = "anthropic"
