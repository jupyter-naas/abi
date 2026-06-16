from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "Perplexity"
    description: str = "Perplexity AI's search-augmented language model for real-time, citation-backed answers."
    logo_url: str = "https://uxwing.com/wp-content/themes/uxwing/download/brands-and-social-media/perplexity-ai-icon.png"
    tags: list[str] = ["perplexity", "search", "language model"]
    slug: str = "perplexity"
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.perplexity
        enabled: true
        config:
            perplexity_api_key: "{{ secret.PERPLEXITY_API_KEY }}"
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
            openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
        """
        perplexity_api_key: str
        openai_api_key: str | None = None
        openrouter_api_key: str | None = None
        datastore_path: str = "perplexity"
