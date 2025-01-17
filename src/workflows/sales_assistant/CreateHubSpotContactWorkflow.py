from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.HubSpotIntegration import HubSpotIntegration, HubSpotIntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from typing import Dict, Optional
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

@dataclass
class CreateHubSpotContactWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateHubSpotContactWorkflow.
    
    Attributes:
        hubspot_integration_config (HubSpotIntegrationConfiguration): Configuration for the HubSpot integration
    """
    hubspot_integration_config: HubSpotIntegrationConfiguration


class CreateHubSpotContactWorkflowParameters(WorkflowParameters):
    """Parameters for CreateHubSpotContactWorkflow.
    
    Attributes:
        email (str): Email address of the contact
        firstname (Optional[str]): First name of the contact
        lastname (Optional[str]): Last name of the contact
        company (Optional[str]): Company name of the contact
        phone (Optional[str]): Phone number of the contact
        jobtitle (Optional[str]): Job title of the contact
        linkedinbio (Optional[str]): LinkedIn URL of the contact
    """
    email: str = Field(..., description="Email address of the contact")
    firstname: Optional[str] = Field(None, description="Optional, First name of the contact")
    lastname: Optional[str] = Field(None, description="Optional, Last name of the contact")
    company: Optional[str] = Field(None, description="Optional, Company name of the contact")
    phone: Optional[str] = Field(None, description="Optional, Phone number of the contact")
    jobtitle: Optional[str] = Field(None, description="Optional, Job title of the contact")
    linkedinbio: Optional[str] = Field(None, description="Optional, LinkedIn URL of the contact")
    
    @property
    def properties(self) -> Dict[str, str]:
        """Convert configuration attributes to HubSpot properties dictionary."""
        properties = {"email": self.email}
        if self.firstname: properties["firstname"] = self.firstname
        if self.lastname: properties["lastname"] = self.lastname
        if self.company: properties["company"] = self.company
        if self.phone: properties["phone"] = self.phone
        if self.jobtitle: properties["jobtitle"] = self.jobtitle
        if self.linkedinbio: properties["linkedinbio"] = self.linkedinbio
        return properties

class CreateHubSpotContactWorkflow(Workflow):
    """Create a new contact in HubSpot with the given properties."""
    __configuration: CreateHubSpotContactWorkflowConfiguration
    
    def __init__(self, configuration: CreateHubSpotContactWorkflowConfiguration):
        self.__configuration = configuration
        self.__hubspot_integration = HubSpotIntegration(self.__configuration.hubspot_integration_config)
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="create_hubspot_contact",
            description="Creates a new contact in HubSpot after checking for existing contacts with the same email",
            func=lambda **kwargs: self.run(CreateHubSpotContactWorkflowParameters(**kwargs)),
            args_schema=CreateHubSpotContactWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("hubspot/create_contact")
        def create_contact(parameters: CreateHubSpotContactWorkflowParameters):
            return self.run(parameters)

    def run(self, parameters: CreateHubSpotContactWorkflowParameters) -> str:
        properties = parameters.properties
        
        # Validate email presence
        if "email" not in properties:
            return "Error: Email is required in contact properties"
        
        email = properties["email"]
        
        try:
            # Try to get existing contact by email
            existing_contact = self.__hubspot_integration.get_contact_by_email(email)
            if existing_contact:
                return f"Contact with email {email} already exists: {existing_contact}"
        except:
            # If get_contact_by_email fails, try searching
            search_results = self.__hubspot_integration.search_objects(
                object_type="contacts",
                query=email,
                properties=["email"]
            )
            
            if not search_results.empty:
                return f"Similar contact(s) found: {search_results.to_dict('records')}"
        
        # Create new contact if no existing contact found
        new_contact = self.__hubspot_integration.create_contact(properties)
        return f"New contact created successfully: {new_contact}"