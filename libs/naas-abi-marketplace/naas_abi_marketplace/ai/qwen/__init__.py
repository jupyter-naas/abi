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
    logo_url: str = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Qwen_logo.svg/3840px-Qwen_logo.svg.png"
    tags: list[str] = ["alibaba", "qwen", "multilingual"]
    slug: str = "qwen"
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
