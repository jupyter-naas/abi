from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "Grok"
    description: str = "xAI's revolutionary AI with the highest intelligence scores globally, designed for truth-seeking and real-world understanding."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/grok.jpg"
    tags: list[str] = ["xai", "grok", "reasoning"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.grok
        enabled: true
        config:
            xai_api_key: "{{ secret.XAI_API_KEY }}"
        """
        xai_api_key: str
        datastore_path: str = "grok"
