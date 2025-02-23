from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class CreateOfferPresentationWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateOfferPresentationWorkflow.
    
    Attributes:
        powerpoint_integration_config (PowerPointIntegrationConfiguration): Configuration for PowerPoint integration
    """
    powerpoint_integration_config: PowerPointIntegrationConfiguration

class CreateOfferPresentationParameters(WorkflowParameters):
    """Parameters for CreateOfferPresentationWorkflow execution.
    
    Attributes:
        client_name (str): Name of the client
        project_name (str): Name of the project
        brief_path (str): Path to the brief document
        output_path (str): Path where to save the generated presentation
    """
    client_name: str = Field(..., description="Name of the client")
    project_name: str = Field(..., description="Name of the project")
    brief_path: str = Field(..., description="Path to the brief document")
    output_path: str = Field(..., description="Path where to save the generated presentation")

class CreateOfferPresentationWorkflow(Workflow):
    __configuration: CreateOfferPresentationWorkflowConfiguration
    
    def __init__(self, configuration: CreateOfferPresentationWorkflowConfiguration):
        self.__configuration = configuration
        self.__powerpoint = PowerPointIntegration(self.__configuration.powerpoint_integration_config)

    def run(self, parameters: CreateOfferPresentationParameters) -> str:
        # Get the template structure
        template_structure = self.__powerpoint.get_organization_template_structure()
        
        # Generate slides based on the brief
        presentation = self.__powerpoint.generate_organization_slides(
            template_structure=template_structure,
            slides_content={
                "title": f"{parameters.client_name} - {parameters.project_name}",
                "subtitle": "Project Proposal",
                # Add more slide content based on the brief
            }
        )
        
        # Save the presentation
        self.__powerpoint.save_presentation(presentation, parameters.output_path)
        return f"Presentation saved at {parameters.output_path}"

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="create_offer_presentation",
            description="Creates a PowerPoint presentation for a client offer based on a brief",
            func=lambda **kwargs: self.run(CreateOfferPresentationParameters(**kwargs)),
            args_schema=CreateOfferPresentationParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/create_offer_presentation")
        def create_presentation(parameters: CreateOfferPresentationParameters):
            return self.run(parameters) 