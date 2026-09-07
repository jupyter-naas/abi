from naas_abi_core.module.ModuleComponentLoader import load_subclasses
from naas_abi_core.workflow.workflow import Workflow


class ModuleWorkflowLoader:
    @classmethod
    def load_workflows(cls, class_: type) -> list[type[Workflow]]:
        return load_subclasses(class_, "workflows", Workflow)
