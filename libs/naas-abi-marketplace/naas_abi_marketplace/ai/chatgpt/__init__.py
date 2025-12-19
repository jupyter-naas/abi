import os

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        openai_api_key: str
        openrouter_api_key: str | None = None

    def on_initialized(self):
        super().on_initialized()
        # We setup the OPENAI_API_KEY environment variable as OpenAI SDK requires it. Also, the IntentMapper will fallback to using OpenAI so it need to be in the environment.
        os.environ["OPENAI_API_KEY"] = self.configuration.openai_api_key
