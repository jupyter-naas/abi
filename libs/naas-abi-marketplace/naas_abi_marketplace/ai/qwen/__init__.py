from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    name: str = "Qwen"
    description: str = "Alibaba Cloud's Qwen language models for multilingual tasks, coding, reasoning, and tool use."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/qwen.jpg"
    tags: list[str] = ["alibaba", "qwen", "multilingual"]
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.qwen
        enabled: true
        config:
            datastore_path: "qwen"
        """
        datastore_path: str = "qwen"
