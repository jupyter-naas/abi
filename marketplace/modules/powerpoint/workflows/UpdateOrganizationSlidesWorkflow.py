from abi.workflow import Workflow, WorkflowConfiguration
from src.core.modules.common.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
    Presentation,
)
from src.core.modules.common.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from src.core.modules.common.integrations.OpenAIIntegration import (
    OpenAIIntegration,
    OpenAIIntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import Field, BaseModel
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
from lib.abi.services.object_storage.ObjectStoragePort import (
    Exceptions as ObjectStorageExceptions,
)
from io import BytesIO
from datetime import datetime
import os


@dataclass
class UpdateOrganizationSlidesWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for PowerPoint Workflow.

    Attributes:
        powerpoint_integration_config (PowerPointIntegrationConfiguration): PowerPoint integration configuration
        openai_integration_config (OpenAIIntegrationConfiguration): OpenAI integration configuration
        naas_integration_config (NaasIntegrationConfiguration): Naas integration configuration
        template_path (str): Path to the PowerPoint template file
        output_dir (str): Path to save the generated presentation
        model_id (str): Naas model id
        temperature (float): Temperature for the completion
    """

    powerpoint_integration_config: PowerPointIntegrationConfiguration
    openai_integration_config: OpenAIIntegrationConfiguration
    naas_integration_config: NaasIntegrationConfiguration
    template_path: str = "assets/OrganizationTemplate.pptx"
    output_dir: str = "datalake/powerpoint-store/update-organization-slides"
    model: str = "o3-mini"


class UpdateOrganizationSlidesWorkflowParameters(WorkflowParameters):
    """Parameters for PowerPoint Update Organization Slides Workflow execution.

    Attributes:
        prompt (str): Prompt to generate the presentation
        number_of_slides (int): Number of slides to generate
        template_path (str): Path to the PowerPoint template
    """

    text: str = Field(
        ..., description="Text to be used to update the presentation framework."
    )
    use_cache: bool = Field(
        True,
        description="Use cache to generate the presentation. By default, it is set to True.",
    )


class UpdateOrganizationSlidesWorkflow(Workflow):
    """Workflow for updating a PowerPoint presentation based on a prompt."""

    __configuration: UpdateOrganizationSlidesWorkflowConfiguration

    def __init__(self, configuration: UpdateOrganizationSlidesWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(
            self.__configuration.powerpoint_integration_config
        )
        self.__openai_integration = OpenAIIntegration(
            self.__configuration.openai_integration_config
        )
        self.__naas_integration = NaasIntegration(
            self.__configuration.naas_integration_config
        )

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

    def convert_input_to_json(
        self,
        input: str,
        output_dir: str,
        prompt: str,
        system_prompt: str,
        template_slides: list[dict],
        response_format: dict,
        use_cache: bool = True,
    ) -> Path:
        """Generate a presentation based on a prompt."""
        # Create hash from prompt to use as unique identifier
        prompt_hash = hashlib.md5(input.encode()).hexdigest()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Create directory if it doesn't exist
        output_dir = os.path.join(output_dir, f"{timestamp}_{prompt_hash}")

        try:
            completion = services.storage_service.get_object(
                output_dir, "presentation.json"
            ).decode("utf-8")
            data = json.loads(completion)
        except ObjectStorageExceptions.ObjectNotFound:
            completion = None
            data = None

        if completion is None or use_cache is False:
            # Create completion
            logger.info("-----> Creating completion")
            completion = self.__openai_integration.create_chat_completion_beta(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.__configuration.model,
                response_format=response_format,
            )

            # Save completion to file
            completion_json = self.extract_json_from_completion(completion)
            data = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "model": self.__configuration.model,
                "response_format": response_format,
                "template_slides": template_slides,
                "completion_text": completion,
                "completion_json": completion_json,
                "output_dir": str(output_dir),
            }

            services.storage_service.put_object(
                prefix=output_dir,
                key="presentation.json",
                content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
            )

        return data

    def save_and_create_asset(
        self, presentation: Presentation, output_dir: Path
    ) -> str:
        # Save presentation
        logger.info("-----> Saving presentation")
        # Create byte stream
        byte_stream = BytesIO()
        presentation.save(byte_stream)
        byte_stream.seek(0)
        services.storage_service.put_object(
            prefix=output_dir, key="presentation.pptx", content=byte_stream.getvalue()
        )

        # Create or update asset
        logger.info("-----> Uploading presentation to storage")
        byte_stream.seek(0)
        asset = self.__naas_integration.upload_asset(
            data=byte_stream.getvalue(),
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix=output_dir,
            object_name=f"{uuid.uuid4().hex}.pptx",
        )
        url = asset.get("asset").get("url")
        if url.endswith("/"):
            url = url[:-1]
        return f"Presentation generated and saved to {url}"

    def get_template_structure(self) -> list[dict]:
        # Load presentation template
        presentation = self.__powerpoint_integration.create_presentation(
            self.__configuration.template_path
        )

        # load slides and shapes with text to be updated: "template" must be in the text
        template_slides = self.__powerpoint_integration.list_slides(
            presentation, text=True
        )
        shapes = [
            {
                "slide_number": slide.get("slide_number"),
                "shape_id": shape.get("shape_id"),
                "shape_type": shape.get("shape_type"),
                "text": shape.get("text"),
            }
            for slide in template_slides
            for shape in slide.get("shapes", [])
            if "template" in shape.get("text", "").lower()
        ]
        return shapes

    def update_slides(
        self, parameters: UpdateOrganizationSlidesWorkflowParameters
    ) -> str:
        # Load presentation template
        presentation = self.__powerpoint_integration.create_presentation(
            self.__configuration.template_path
        )

        # load slides and shapes with text to be updated: "template" must be in the text
        template_slides = self.__powerpoint_integration.list_slides(
            presentation, text=True
        )
        shapes = [
            {
                "slide_number": slide.get("slide_number"),
                "shape_id": shape.get("shape_id"),
                "shape_type": shape.get("shape_type"),
                "text": shape.get("text"),
            }
            for slide in template_slides
            for shape in slide.get("shapes", [])
            if "template" in shape.get("text", "").lower()
        ]

        # Create prompt to update the presentation
        prompt = f"""Generate a PowerPoint presentation from the following text: 
        ```text
        {parameters.text}
        ```
        Rules:
        - Do NOT create new slides.
        - Use your internal knowledge to update if the initial input text does not have enough information to generate the presentation.
        - Generate all shapes and all slides

        Use the following template slides as a reference: 
        ```json
        {shapes}
        ```
        """

        # Create system prompt to generate the presentation
        system_prompt = """
        You are a PowerPoint presentation generator. 
        You are given a text and a template presentation structure.
        Please output a JSON object containing the following fields: 
        ```json
        {{
            "shapes": [
                {{
                    "slide_number": int,
                    "shape_id": int,
                    "shape_type": int,
                    "text": str,
                    "new_text": str
                }}
            ]
        }}
        ```
        """

        # Generate new structure of the presentation
        completion_json = self.convert_input_to_json(
            parameters.text,
            self.__configuration.output_dir,
            prompt,
            system_prompt,
            template_slides,
            response_format={"type": "json_object"},
            use_cache=parameters.use_cache,
        )

        # Update slides in presentation
        logger.info("-----> Updating slides in presentation")
        for data in completion_json.get("completion_json", {}).get("shapes", []):
            self.__powerpoint_integration.update_shape(
                presentation=presentation,
                slide_index=data.get("slide_number"),
                shape_id=data.get("shape_id"),
                text=data.get("new_text"),
            )

        # Save presentation and create asset
        return self.save_and_create_asset(
            presentation, completion_json.get("output_dir")
        )

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="powerpoint_generate_organization_slides",
                description=f"Generate slides from a user brief for an given organization using the template presentation {self.__configuration.template_path}. Map the brief to the presentation structure provided by the tool 'powerpoint_get_organization_template_structure'.",
                func=lambda **kwargs: self.update_slides(
                    UpdateOrganizationSlidesWorkflowParameters(**kwargs)
                ),
                args_schema=UpdateOrganizationSlidesWorkflowParameters,
            ),
            StructuredTool(
                name="powerpoint_get_organization_template_structure",
                description=f"Get the structure of the Organization template presentation {self.__configuration.template_path} to help user creating a detailed brief based on information required to generate a PowerPoint presentation.",
                func=self.get_template_structure,
                args_schema=None,
            ),
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
