from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class CreateOfferPresentationWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateOfferPresentationWorkflow.
    
    Attributes:
        powerpoint_integration_config (PowerPointIntegrationConfiguration): Configuration for the PowerPoint integration
    """
    powerpoint_integration_config: PowerPointIntegrationConfiguration

class CreateOfferPresentationWorkflowParameters(WorkflowParameters):
    """Parameters for CreateOfferPresentationWorkflow execution.
    
    Attributes:
        company_name (str): Name of the company for which to create the offer presentation
        services (List[str]): List of services to include in the offer
        duration (str): Duration of the proposed offer
        price (str): Price for the proposed offer
    """
    company_name: str = Field(..., description="Name of the company for which to create the offer presentation")
    services: List[str] = Field(..., description="List of services to include in the offer")
    duration: str = Field(..., description="Duration of the proposed offer")
    price: str = Field(..., description="Price for the proposed offer")

class CreateOfferPresentationWorkflow(Workflow):
    __configuration: CreateOfferPresentationWorkflowConfiguration
    
    def __init__(self, configuration: CreateOfferPresentationWorkflowConfiguration):
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(self.__configuration.powerpoint_integration_config)

    def run(self, parameters: CreateOfferPresentationWorkflowParameters) -> Any:
        """Create a PowerPoint presentation for a client offer.
        
        Args:
            parameters: Parameters for the workflow
            
        Returns:
            Dict: Information about the created presentation
        """
        # Implementation of the workflow
        # This is a placeholder implementation - you'll need to replace this with actual logic
        logger.info(f"Creating offer presentation for {parameters.company_name}")
        
        # Example implementation
        presentation = {
            "company_name": parameters.company_name,
            "slides": [
                {"title": "Introduction", "content": f"Offer for {parameters.company_name}"},
                {"title": "Services", "content": f"Services: {', '.join(parameters.services)}"},
                {"title": "Duration", "content": f"Duration: {parameters.duration}"},
                {"title": "Pricing", "content": f"Price: {parameters.price}"}
            ]
        }
        
        # Actual implementation would use the PowerPoint integration to create the presentation
        # return self.__powerpoint_integration.create_presentation(presentation)
        
        return {"status": "created", "presentation": presentation}

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="powerpoint_create_offer_presentation",
            description="Creates a PowerPoint presentation for a client offer with company details, services, duration, and pricing",
            func=lambda **kwargs: self.run(CreateOfferPresentationWorkflowParameters(**kwargs)),
            args_schema=CreateOfferPresentationWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/powerpoint/create-offer")
        def create_offer_presentation(parameters: CreateOfferPresentationWorkflowParameters):
            return self.run(parameters) 