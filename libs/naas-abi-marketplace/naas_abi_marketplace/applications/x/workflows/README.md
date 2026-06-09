from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field

@dataclass
class XWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for X workflow."""


    pass

class XWorkflowParameters(WorkflowParameters):
    """Parameters for X workflow."""

    pass

    # example_parameter: Annotated[
    #     str,
    #     Field(
    #         ...,
    #         description="Description of the example parameter",
    #         example="Example value",
    #     ),
    # ]


class XWorkflow(Workflow[XWorkflowParameters]):
    """Workflow for X."""

    __configuration: XWorkflowConfiguration

    def __init__(self, configuration: XWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(
        self, parameters: XWorkflowParameters
    ) -> dict | list[dict]:
        # Implement the workflow logic here
        pass


    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="X",
                description="Description of what the workflow does",
                func=lambda **kwargs: self.run(
                    XWorkflowParameters(**kwargs)
                ),
                args_schema=XWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None