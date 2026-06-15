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
    name: str = "Amazon Bedrock"
    description: str = "Amazon Bedrock managed service for foundation models through a unified AWS API."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/bedrock.png"
    tags: list[str] = ['aws', 'bedrock', 'foundation models']
    slug: str = "amazon-bedrock"
    privacy_policy_url: str = "https://aws.amazon.com/privacy"
    terms_of_service_url: str = "https://aws.amazon.com/service-terms/"
    status_page_url: Optional[str] = 'https://health.aws.amazon.com/health/status'
    headquarters: str = "US"
    datacenters: Optional[list] = None

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.amazon_bedrock
        enabled: true
        config:
            amazon_bedrock_api_key: "{{ secret.AMAZON_BEDROCK_API_KEY }}"
            datastore_path: "amazon_bedrock"
        """

        amazon_bedrock_api_key: str
        datastore_path: str = "amazon_bedrock"
