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
    name: str = "OpenRouter"
    description: str = "OpenRouter unified API gateway for accessing multiple AI model providers with a single API key."
    logo_url: str = "https://pbs.twimg.com/profile_images/1682268668321726464/NEb6_n7n_400x400.jpg"
    slug: str = "openrouter"
    tags: list[str] = ["openrouter", "api gateway", "multi-model"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.openrouter
        enabled: true
        config:
            openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
            datastore_path: "openrouter"
        """

        openrouter_api_key: str
        datastore_path: str = "openrouter"

    def on_load(self):
        super().on_load()
