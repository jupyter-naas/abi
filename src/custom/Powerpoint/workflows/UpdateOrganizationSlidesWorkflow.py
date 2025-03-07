from abi.workflow import Workflow, WorkflowConfiguration
from src.custom.Powerpoint.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.core.integrations.OpenAIIntegration import OpenAIIntegration, OpenAIIntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from abi import logger
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pathlib import Path
import json
from src import config
import hashlib
import uuid
from src.services import services
from lib.abi.services.object_storage.ObjectStoragePort import Exceptions as ObjectStorageExceptions
from io import BytesIO
from datetime import datetime
import os

@dataclass
class UpdateOrganizationSlidesWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for PowerPoint Workflow.
    
    Attributes:
        powerpoint_integration_config (PowerPointIntegrationConfiguration): PowerPoint integration configuration
        naas_integration_config (NaasIntegrationConfiguration): Naas integration configuration
        template_path (str): Path to the PowerPoint template file
        output_dir (str): Path to save the generated presentation
        model_id (str): Naas model id
        temperature (float): Temperature for the completion
    """
    powerpoint_integration_config: PowerPointIntegrationConfiguration
    naas_integration_config: NaasIntegrationConfiguration
    template_path: str = "assets/PresentationTemplate_FM.pptx"
    output_dir: str = "datalake/powerpoint-store/update-organization-slides"
    model_id: str = "113f2201-9f0e-4bf1-a25f-3ea8ba88e41d"
    temperature: float = 0.3

class UpdateOrganizationSlidesWorkflowParameters(WorkflowParameters):
    """Parameters for PowerPoint Update Organization Slides Workflow execution.
    
    Attributes:
        text (str): Text content to generate slides from
    """
    text: str = Field(..., description="Text content to generate organization slides from")

class UpdateOrganizationSlidesWorkflow(Workflow):
    """Workflow for updating a PowerPoint presentation based on a prompt."""
    __configuration: UpdateOrganizationSlidesWorkflowConfiguration
    
    def __init__(self, configuration: UpdateOrganizationSlidesWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(self.__configuration.powerpoint_integration_config)
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def extract_json_from_completion(self, completion_text: str) -> dict:
        """Extract JSON object from completion text that contains markdown formatting.
        
        Args:
            completion_text (str): Raw completion text containing JSON in markdown format
            
        Returns:
            dict: Parsed JSON object
        """
        # Find JSON content between ```json and ``` markers
        json_start = completion_text.find("```json\n") + len("```json\n")
        json_end = completion_text.rfind("\n```")
        
        if json_start == -1 or json_end == -1:
            json_str = completion_text
        else:
            json_str = completion_text[json_start:json_end]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON: {str(e)}.")
            return {}
    
    def save_and_create_asset(self, presentation, output_dir: Path) -> str:
        # Save presentation
        logger.info("-----> Saving presentation")
        # Create byte stream
        byte_stream = BytesIO() 
        presentation.save(byte_stream)
        byte_stream.seek(0)
        services.storage_service.put_object(
            prefix=output_dir,
            key="presentation.pptx",
            content=byte_stream.getvalue()
        )

        # Create or update asset
        logger.info("-----> Uploading presentation to storage")
        byte_stream.seek(0)
        asset = self.__naas_integration.upload_asset(
            data=byte_stream.getvalue(),
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix=output_dir,
            object_name=f'{uuid.uuid4().hex}.pptx'
        )
        return f"Presentation generated and saved to {asset.get('asset').get('url')}"
    
    def get_template_structure(self) -> list[dict]:
        # Load presentation template
        presentation = self.__powerpoint_integration.create_presentation(self.__configuration.template_path)

        # Load all slides and shapes with their text as examples
        template_slides = self.__powerpoint_integration.list_slides(presentation, text=True)
        shapes = []
        for slide in template_slides:
            slide_shapes = []
            for shape in slide.get("shapes", []):
                if shape.get("text", "").strip():  # Only include shapes that have text
                    slide_shapes.append({
                        "slide_number": slide.get("slide_number"),
                        "shape_id": shape.get("shape_id"),
                        "shape_type": shape.get("shape_type"),
                        "text": shape.get("text")
                    })
            if slide_shapes:
                shapes.extend(slide_shapes)
        return shapes
    
    def update_slides(self, parameters: UpdateOrganizationSlidesWorkflowParameters) -> str:
        presentation = self.__powerpoint_integration.create_presentation(self.__configuration.template_path)
        shapes = self.get_template_structure()

        # Create prompt to update the presentation
        prompt = f"""Generate a PowerPoint presentation from the following text: 
        ```text
        {parameters.text}
        ```
        Rules:
        - Follow the exact same structure as the example template
        - Each shape in the template contains example content - use it as a reference for style and structure
        - Generate new content that matches the style and structure of the example, but about the topic provided
        - Keep the same professional tone and formatting as the example
        - Generate content for all shapes in all slides

        The template contains example content for reference. Here are the slides and their content: 
        ```json
        {shapes}
        ```

        For each shape, generate new content that:
        1. Matches the style and structure of the example text
        2. Contains information about the provided topic
        3. Maintains the same level of detail and professionalism
        
        Return the updated content for each shape in the following JSON format:
        ```json
        [
            {
                "slide_number": 1,
                "shape_id": 1, 
                "text": "New content for shape 1"
            },
            {
                "slide_number": 1,
                "shape_id": 2,
                "text": "New content for shape 2"
            }
        ]
        ```
        Only include shapes that should be updated with text.
        """

        # Get a model to use
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(
            model="gpt-4",
            temperature=self.__configuration.temperature,
            api_key=self.__configuration.openai_integration_config.api_key
        )
        
        # Generate content using the model
        logger.info("-----> Generating content using model")
        completion = model.invoke(prompt)
        logger.debug(f"Completion: {completion}")
        
        # Extract updated content
        logger.info("-----> Extracting content from completion")
        content_updates = self.extract_json_from_completion(completion.content)
        logger.debug(f"Extracted content: {content_updates}")
        
        if not isinstance(content_updates, list):
            return "Error: Failed to generate presentation content. The model did not return valid JSON."
        
        # Apply updates to presentation
        logger.info("-----> Applying updates to presentation")
        slide_shapes = {}
        
        for slide in presentation.slides:
            slide_number = presentation.slides.index(slide) + 1
            slide_shapes[slide_number] = list(slide.shapes)
        
        for update in content_updates:
            slide_number = update.get("slide_number")
            shape_id = update.get("shape_id")
            text = update.get("text")
            
            if not (slide_number and shape_id and text):
                continue
            
            if slide_number not in slide_shapes:
                continue
            
            if shape_id <= 0 or shape_id > len(slide_shapes[slide_number]):
                continue
            
            shape = slide_shapes[slide_number][shape_id - 1]
            
            if hasattr(shape, "text_frame"):
                shape.text_frame.text = text
        
        # Save and create asset
        logger.info("-----> Saving and creating asset")
        return self.save_and_create_asset(presentation, self.__configuration.output_dir)
    
    def run(self, parameters: UpdateOrganizationSlidesWorkflowParameters) -> str:
        """Run the workflow to update organization slides.
        
        Args:
            parameters: Parameters containing the text to generate slides from
            
        Returns:
            str: URL to the generated presentation
        """
        return self.update_slides(parameters)
    
    def powerpoint_get_organization_template_structure(self) -> str:
        """Get the structure of the organization PowerPoint template.
        
        Returns:
            str: JSON string containing the template structure
        """
        shapes = self.get_template_structure()
        return json.dumps(shapes, indent=2)
    
    def powerpoint_generate_organization_slides(self, parameters: UpdateOrganizationSlidesWorkflowParameters) -> str:
        """Generate organization slides based on the provided text.
        
        Args:
            parameters: Parameters containing the text to generate slides from
            
        Returns:
            str: URL to the generated presentation
        """
        return self.update_slides(parameters)
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tools
        """
        class GetOrganizationTemplateStructureSchema(BaseModel):
            pass
            
        return [
            StructuredTool(
                name="powerpoint_get_organization_template_structure",
                description="Get the structure of the organization PowerPoint template",
                func=lambda **kwargs: self.powerpoint_get_organization_template_structure(),
                args_schema=GetOrganizationTemplateStructureSchema
            ),
            StructuredTool(
                name="powerpoint_generate_organization_slides",
                description="Generate organization slides based on the provided text",
                func=lambda **kwargs: self.powerpoint_generate_organization_slides(UpdateOrganizationSlidesWorkflowParameters(**kwargs)),
                args_schema=UpdateOrganizationSlidesWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/update-organization-slides")
        def update_organization_slides(parameters: UpdateOrganizationSlidesWorkflowParameters):
            return self.update_slides(parameters)
            
        @router.get("/organization-template-structure")
        def get_organization_template_structure():
            return self.get_template_structure() 