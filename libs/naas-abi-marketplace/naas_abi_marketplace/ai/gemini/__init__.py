from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


class ABIModule(BaseModule):
    name: str = "Gemini"
    description: str = "Google's multimodal AI model with image generation capabilities, thinking capabilities, and well-rounded performance."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/gemini.png"
    tags: list[str] = ["google", "gemini", "multimodal"]
    slug: str = "gemini"
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[ObjectStorageService])

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.gemini
        enabled: true
        config:
            gemini_api_key: "{{ secret.GEMINI_API_KEY }}"
        """
        gemini_api_key: str
        datastore_path: str = "gemini"
        
