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
class {{workflow_name_pascal}}WorkflowConfiguration(WorkflowConfiguration):
    """Configuration for {{workflow_name_pascal}} workflow."""


    pass

class {{workflow_name_pascal}}WorkflowParameters(WorkflowParameters):
    """Parameters for {{workflow_name_pascal}} workflow."""

    pass

    # example_parameter: Annotated[
    #     str,
    #     Field(
    #         ...,
    #         description="Description of the example parameter",
    #         example="Example value",
    #     ),
    # ]


class {{workflow_name_pascal}}Workflow(Workflow[{{workflow_name_pascal}}WorkflowParameters]):
    """Workflow for {{workflow_name_pascal}}."""

    __configuration: {{workflow_name_pascal}}WorkflowConfiguration

    def __init__(self, configuration: {{workflow_name_pascal}}WorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(
        self, parameters: {{workflow_name_pascal}}WorkflowParameters
    ) -> dict | list[dict]:
        # Implement the workflow logic here
        pass


    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="{{workflow_name_pascal}}",
                description="Description of what the workflow does",
                func=lambda **kwargs: self.run(
                    {{workflow_name_pascal}}WorkflowParameters(**kwargs)
                ),
                args_schema={{workflow_name_pascal}}WorkflowParameters,
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
