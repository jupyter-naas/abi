"""Workflows of a remote module, written like ``naas_abi_core.workflow``'s.

A workflow is business logic behind ``await run(parameters)``: it returns a
JSON-serializable value or a pydantic model. Put it under the package's
``workflows/`` folder; ``BaseModule`` builds it, and the module's agents call it
through ``as_tools()``. Needs ``pip install 'naas-abi-sdk[workflows]'``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

from naas_abi_sdk.processes import Process, ProcessConfiguration, ProcessParameters


@dataclass
class WorkflowConfiguration(ProcessConfiguration):
    pass


class WorkflowParameters(ProcessParameters):
    pass


P = TypeVar("P", bound=WorkflowParameters)


class Workflow(Process, Generic[P]):
    """A sequence of operations a module exposes as an agent tool.

    Subclass it with its parameters model, ``class Greet(Workflow[GreetParameters])``,
    and write ``async def run(self, parameters: GreetParameters)``. The class
    docstring is the tool's description.
    """

    kind: ClassVar[str] = "workflow"
    _configuration_base: ClassVar[type] = WorkflowConfiguration
    _parameters_base: ClassVar[type[ProcessParameters]] = WorkflowParameters

    async def run(self, parameters: P) -> Any:
        raise NotImplementedError(f"{type(self).__name__}.run is not implemented")
