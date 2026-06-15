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
    name: str = "Nvidia"
    description: str = "NVIDIA NIM for deploying optimized AI models on NVIDIA accelerated infrastructure."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/nvidia.png"
    tags: list[str] = ['nvidia', 'nim', 'foundation models']
    slug: str = "nvidia"
    privacy_policy_url: str = "https://www.nvidia.com/en-us/about-nvidia/privacy-policy/"
    terms_of_service_url: str = "https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf"
    status_page_url: Optional[str] = None
    headquarters: str = "US"
    datacenters: Optional[list] = ['US']

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.nvidia
        enabled: true
        config:
            nvidia_api_key: "{{ secret.NVIDIA_API_KEY }}"
            datastore_path: "nvidia"
        """

        nvidia_api_key: str
        datastore_path: str = "nvidia"
