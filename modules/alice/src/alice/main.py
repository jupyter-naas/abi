from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from abi.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import model_validator


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["bob"],
        services=[
            ObjectStorageService
            # TripleStoreService,
            # VectorStoreService,
            # Secret,
        ],
    )

    class Configuration(ModuleConfiguration):
        openai_api_key: str

        @model_validator(mode="after")
        def validate_openai_api_key(self):
            if not self.openai_api_key:
                raise ValueError("openai_api_key must be provided")
            return self
