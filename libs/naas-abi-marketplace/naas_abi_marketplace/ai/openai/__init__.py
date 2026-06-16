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
    logo_url: str = "https://logosandtypes.com/wp-content/uploads/2022/07/OpenAI.png"
    tags: list[str] = ['openai', 'gpt', 'language model']
    slug: str = "openai"
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
