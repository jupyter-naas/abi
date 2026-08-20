from naas_abi_core.module.ModuleComponentLoader import load_subclasses
from naas_abi_core.pipeline.pipeline import Pipeline


class ModulePipelineLoader:
    @classmethod
    def load_pipelines(cls, class_: type) -> list[type[Pipeline]]:
        return load_subclasses(class_, "pipelines", Pipeline)
