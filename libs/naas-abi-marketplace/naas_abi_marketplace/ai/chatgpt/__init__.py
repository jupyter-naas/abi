import os

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[], 
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.chatgpt
        enabled: true
        config:
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
            openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
        """
        openai_api_key: str
        openrouter_api_key: str | None = None
        datastore_path: str = "chatgpt"

    def on_initialized(self):
        super().on_initialized()
        # We setup the OPENAI_API_KEY environment variable as OpenAI SDK requires it. Also, the IntentMapper will fallback to using OpenAI so it need to be in the environment.
        os.environ["OPENAI_API_KEY"] = self.configuration.openai_api_key
