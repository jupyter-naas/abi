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
    name: str = "Mistral"
    description: str = "Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/mistral.png"
    tags: list[str] = ['mistral', 'code', 'language model']
    slug: str = "mistral"
    privacy_policy_url: str = "https://mistral.ai/terms/#privacy-policy"
    terms_of_service_url: str = "https://mistral.ai/terms/#terms-of-use"
    status_page_url: Optional[str] = 'https://status.mistral.ai/'
    headquarters: str = "FR"
    datacenters: Optional[list] = None

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.mistral
        enabled: true
        config:
            mistral_api_key: "{{ secret.MISTRAL_API_KEY }}"
            datastore_path: "mistral"
        """

        mistral_api_key: str
        datastore_path: str = "mistral"
