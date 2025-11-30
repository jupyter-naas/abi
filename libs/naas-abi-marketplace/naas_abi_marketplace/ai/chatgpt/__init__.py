from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from pydantic import model_validator


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        openai_api_key: str | None = None
        openrouter_api_key: str | None = None

        @model_validator(mode="after")
        def validate_configuration(self):
            if self.openai_api_key is None and self.openrouter_api_key is None:
                raise ValueError(
                    "OPENAI_API_KEY or OPENROUTER_API_KEY must be provided"
                )
            if self.global_config.ai_mode == "cloud" and (
                not self.openai_api_key and not self.openrouter_api_key
            ):
                raise ValueError(
                    "if AI_MODE is cloud, OPENAI_API_KEY and OPENROUTER_API_KEY must be provided"
                )
            return self

    @property
    def instance(self) -> "ABIModule":
        return self.get_instance()
