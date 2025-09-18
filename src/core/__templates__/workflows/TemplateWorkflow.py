from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.__templates__.integrations.TemplateIntegration import (
    YourIntegration,
    YourIntegrationConfiguration
)
from dataclasses import dataclass
from pydantic import Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import Any
from enum import Enum

@dataclass
class YourWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for YourWorkflow.
    
    Attributes:
        integration_config (YourIntegrationConfiguration): Configuration for the integration
    """
    integration_config: YourIntegrationConfiguration

class YourWorkflowParameters(WorkflowParameters):
    """Parameters for YourWorkflow execution.
    
    Attributes:
        parameter_1 (str): Description of parameter_1
        parameter_2 (int): Description of parameter_2
    """
    parameter_1: str = Field(..., description="Description of parameter_1")
    parameter_2: int = Field(..., description="Description of parameter_2")

class YourWorkflow(Workflow):
    __configuration: YourWorkflowConfiguration
    
    def __init__(self, configuration: YourWorkflowConfiguration):
        self.__configuration = configuration
        self.__integration = YourIntegration(self.__configuration.integration_config)

    def run_workflow(self, parameters: YourWorkflowParameters) -> Any:
        return self.__integration.example_method(parameters.parameter_1)

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="your_workflow",
                description="Executes the workflow with the given parameters",
                func=lambda **kwargs: self.run(YourWorkflowParameters(**kwargs)),
                args_schema=YourWorkflowParameters
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