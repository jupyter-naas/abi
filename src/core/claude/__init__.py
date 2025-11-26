from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from pydantic import model_validator


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        anthropic_api_key: str | None = None
        openrouter_api_key: str | None = None

        @model_validator(mode="after")
        def validate_configuration(self):
            if self.anthropic_api_key is None and self.openrouter_api_key is None:
                raise ValueError(
                    "ANTHROPIC_API_KEY or OPENROUTER_API_KEY must be provided"
                )
            if self.global_config.ai_mode == "cloud" and (
                not self.anthropic_api_key and not self.openrouter_api_key
            ):
                raise ValueError(
                    "if AI_MODE is cloud, ANTHROPIC_API_KEY and OPENROUTER_API_KEY must be provided"
                )
            return self
