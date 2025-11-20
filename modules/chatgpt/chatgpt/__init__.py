from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from abi.services.secret.Secret import Secret
from pydantic import Field, model_validator


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["alice"], services=[]
    )

    class Configuration(ModuleConfiguration):
        openai_api_key: str

        @model_validator(mode="after")
        def validate_openai_api_key(self):
            if self.openai_api_key == "None":
                raise ValueError("openai_api_key must be provided and not empty")
            return self
