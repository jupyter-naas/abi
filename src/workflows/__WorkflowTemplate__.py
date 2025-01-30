from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations import YourIntegration, YourIntegrationConfiguration
from src import config, secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any

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

    def run(self, parameters: YourWorkflowParameters) -> Any:
        # Add your workflow logic here
        return "Your result"

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="your_workflow_name",
            description="Description of what your workflow does",
            func=lambda **kwargs: self.run(YourWorkflowParameters(**kwargs)),
            args_schema=YourWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/your_endpoint")
        def run_workflow(parameters: YourWorkflowParameters):
            return self.run(parameters)

if __name__ == "__main__":
    from src.integrations import YourIntegration, YourIntegrationConfiguration
    
    # Initialize integration
    integration = YourIntegration(YourIntegrationConfiguration(attribute_1=secret.get("YOUR_SECRET_1"), attribute_2=secret.get("YOUR_SECRET_2")))
    
    # Initialize configuration
    configuration = YourWorkflowConfiguration(integration=integration)
    
    # Initialize workflow
    workflow = YourWorkflow(configuration)

    # Run workflow
    result = workflow.run(YourWorkflowParameters(parameter_1="value1", parameter_2=123))