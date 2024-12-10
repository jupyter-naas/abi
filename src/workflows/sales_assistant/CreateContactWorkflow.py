from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.HubSpotIntegration import HubSpotIntegration, HubSpotIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Dict, Optional

@dataclass
class CreateContactWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating new HubSpot contact with validation.
    
    Attributes:
        hubspot_integration_config: Configuration for HubSpot API
        email (str): Email address of the contact
        firstname (Optional[str]): First name of the contact
        lastname (Optional[str]): Last name of the contact
        company (Optional[str]): Company name of the contact
        phone (Optional[str]): Phone number of the contact
        jobtitle (Optional[str]): Job title of the contact
        linkedinbio (Optional[str]): LinkedIn URL of the contact
    """
    hubspot_integration_config: HubSpotIntegrationConfiguration
    email: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    jobtitle: Optional[str] = None
    linkedinbio: Optional[str] = None

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

class CreateContactWorkflow(Workflow):
    __configuration: CreateContactWorkflowConfiguration
    
    def __init__(self, configuration: CreateContactWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__hubspot_integration = HubSpotIntegration(
            self.__configuration.hubspot_integration_config
        )
    
    def run(self) -> str:
        properties = self.__configuration.properties
        
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

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.post("/create_contact")
    def create_contact(
        email: str,
        firstname: Optional[str] = None,
        lastname: Optional[str] = None,
        company: Optional[str] = None,
        phone: Optional[str] = None,
        jobtitle: Optional[str] = None,
        linkedinbio: Optional[str] = None
    ):
        configuration = CreateContactWorkflowConfiguration(
            hubspot_integration_config=HubSpotIntegrationConfiguration(
                access_token=secret.get('HUBSPOT_ACCESS_TOKEN')
            ),
            email=email,
            firstname=firstname,
            lastname=lastname,
            company=company,
            phone=phone,
            jobtitle=jobtitle,
            linkedinbio=linkedinbio
        )
        workflow = CreateContactWorkflow(configuration)
        return workflow.run()
    
    uvicorn.run(app, host="0.0.0.0", port=9878)

def main():
    configuration = CreateContactWorkflowConfiguration(
        hubspot_integration_config=HubSpotIntegrationConfiguration(
            access_token=secret.get('HUBSPOT_ACCESS_TOKEN')
        ),
        email="test@example.com",
        firstname="Test",
        lastname="User",
        company="Test Company",
        phone="1234567890",
        jobtitle="Test Job Title",
        linkedinbio="https://www.linkedin.com/in/testuser"
    )
    workflow = CreateContactWorkflow(configuration)
    result = workflow.run()
    print(result)

def as_tool():
    from langchain_core.tools import StructuredTool
    
    class CreateContactSchema(BaseModel):
        email: str = Field(..., description="Email address of the contact")
        firstname: Optional[str] = Field(None, description="Optional, First name of the contact")
        lastname: Optional[str] = Field(None, description="Optional, Last name of the contact")
        company: Optional[str] = Field(None, description="Optional, Company name of the contact")
        phone: Optional[str] = Field(None, description="Optional, Phone number of the contact")
        jobtitle: Optional[str] = Field(None, description="Optional, Job title of the contact")
        linkedinbio: Optional[str] = Field(None, description="Optional, LinkedIn URL of the contact")

    def create_contact_tool(
        email: str,
        firstname: Optional[str] = None,
        lastname: Optional[str] = None,
        company: Optional[str] = None,
        phone: Optional[str] = None,
        jobtitle: Optional[str] = None,
        linkedinbio: Optional[str] = None
    ) -> str:
        configuration = CreateContactWorkflowConfiguration(
            hubspot_integration_config=HubSpotIntegrationConfiguration(
                access_token=secret.get('HUBSPOT_ACCESS_TOKEN')
            ),
            email=email,
            firstname=firstname,
            lastname=lastname,
            company=company,
            phone=phone,
            jobtitle=jobtitle,
            linkedinbio=linkedinbio
        )
        workflow = CreateContactWorkflow(configuration)
        return workflow.run()
    
    return StructuredTool(
        name="create_hubspot_contact",
        description="Creates a new contact in HubSpot after checking for existing contacts with the same email",
        func=lambda **kwargs: create_contact_tool(**kwargs),
        args_schema=CreateContactSchema
    )

if __name__ == "__main__":
    main()