from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
# from pydantic import model_validator


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.claude
        enabled: true
        config:
            anthropic_api_key: "{{ secret.ANTHROPIC_API_KEY }}"
        """

        anthropic_api_key: str
        datastore_path: str = "claude"

        # @model_validator(mode="after")
        # def validate_configuration(self):
        #     if self.anthropic_api_key is None and self.openrouter_api_key is None:
        #         raise ValueError(
        #             "ANTHROPIC_API_KEY or OPENROUTER_API_KEY must be provided"
        #         )
        #     if self.global_config.ai_mode == "cloud" and (
        #         not self.anthropic_api_key and not self.openrouter_api_key
        #     ):
        #         raise ValueError(
        #             "if AI_MODE is cloud, ANTHROPIC_API_KEY and OPENROUTER_API_KEY must be provided"
        #         )
        #     return self
