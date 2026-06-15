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
    name: str = "OpenAI"
    description: str = "OpenAI's API for GPT models, embeddings, and image generation capabilities."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/openai.png"
    tags: list[str] = ['openai', 'gpt', 'language model']
    slug: str = "openai"
    privacy_policy_url: str = "https://openai.com/policies/privacy-policy/"
    terms_of_service_url: str = "https://openai.com/policies/row-terms-of-use/"
    status_page_url: Optional[str] = 'https://status.openai.com/'
    headquarters: str = "US"
    datacenters: Optional[list] = None

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.openai
        enabled: true
        config:
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
            datastore_path: "openai"
        """

        openai_api_key: str
        datastore_path: str = "openai"
