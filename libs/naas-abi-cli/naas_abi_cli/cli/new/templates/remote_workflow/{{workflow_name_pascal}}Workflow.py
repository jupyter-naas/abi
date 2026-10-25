"""{{workflow_name_pascal}}Workflow: a workflow of this remote module.

Written like an in-engine workflow, on ``naas_abi_sdk`` only. ``ABIModule`` finds
it under ``workflows/`` and builds it once ``on_initialized`` has run, and the
module's agents call it as a tool:

    tools = self.get_workflow("{{workflow_name_snake}}_workflow").as_tools()

Its name, ``{{workflow_name_snake}}_workflow``, is the class name in snake case.
Built with an empty ``{{workflow_name_pascal}}WorkflowConfiguration`` unless it
needs more: define ``New(module)`` on the class (sync or async; read credentials
with ``await module.engine.services.secret.get("KEY")``), or bind an instance in
``on_initialized`` with ``self.expose_workflow(name, instance)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import Field


@dataclass
class {{workflow_name_pascal}}WorkflowConfiguration(WorkflowConfiguration):
    """Configuration for {{workflow_name_pascal}}Workflow."""


class {{workflow_name_pascal}}WorkflowParameters(WorkflowParameters):
    """Parameters for {{workflow_name_pascal}}Workflow: the tool's arguments."""

    message: str = Field(default="hello", description="Text the workflow echoes back")


class {{workflow_name_pascal}}Workflow(Workflow[{{workflow_name_pascal}}WorkflowParameters]):
    """Echoes a message. Replace with what the workflow does: this text is the
    description an agent reads to decide when to call it."""

    __configuration: {{workflow_name_pascal}}WorkflowConfiguration

    def __init__(self, configuration: {{workflow_name_pascal}}WorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    async def run(
        self, parameters: {{workflow_name_pascal}}WorkflowParameters
    ) -> dict[str, Any]:
        # Return a JSON-serializable value or a pydantic model.
        return {"message": parameters.message}
