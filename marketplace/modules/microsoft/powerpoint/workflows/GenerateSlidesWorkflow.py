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
from src.services import services, ObjectStorageExceptions
from io import BytesIO


@dataclass
class GenerateSlidesWorkflowConfiguration(WorkflowConfiguration):
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
    template_path: str = "assets/PresentationTemplate.pptx"
    output_dir: str = "datalake/powerpoint-store/generate-slides"
    model_id: str = "113f2201-9f0e-4bf1-a25f-3ea8ba88e41d"
    temperature: float = 0.3


class GenerateSlidesWorkflowParameters(WorkflowParameters):
    """Parameters for PowerPoint Generate Presentation Workflow execution.

    Attributes:
        prompt (str): Prompt to generate the presentation
        number_of_slides (int): Number of slides to generate
        template_path (str): Path to the PowerPoint template
    """

    prompt: str = Field(
        ...,
        description="Prompt to generate the presentation. Make sure you include all information needed to generate the presentation.",
    )
    number_of_slides: int = Field(5, description="Number of slides to generate.")
    use_cache: bool = Field(
        True,
        description="Use cache to generate the presentation. By default, it is set to True.",
    )


class GenerateSlidesWorkflow(Workflow):
    """Workflow for generating a PowerPoint presentation based on a prompt."""

    __configuration: GenerateSlidesWorkflowConfiguration

    def __init__(self, configuration: GenerateSlidesWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(
            self.__configuration.powerpoint_integration_config
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
        use_cache: bool = True,
    ) -> Path:
        """Generate a presentation based on a prompt."""
        # Create hash from prompt to use as unique identifier
        prompt_hash = hashlib.md5(input.encode()).hexdigest()

        # Create directory if it doesn't exist
        output_dir = Path(output_dir) / prompt_hash

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
            completion = self.__naas_integration.create_completion(
                model_id=self.__configuration.model_id,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=self.__configuration.temperature,
            )

            # Save completion to file
            completion_json = self.extract_json_from_completion(completion)
            data = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "model_id": self.__configuration.model_id,
                "temperature": self.__configuration.temperature,
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

    def generate_slides(self, parameters: GenerateSlidesWorkflowParameters) -> str:
        # Load presentation template
        presentation = self.__powerpoint_integration.create_presentation(
            self.__configuration.template_path
        )

        # load slides and shapes
        template_slides = self.__powerpoint_integration.list_slides(
            presentation, text=True
        )

        # Create prompt to generate the presentation
        prompt = f"""
        {parameters.prompt}
        Create {parameters.number_of_slides} slides.
        Only use input text to generate the presentation.
        Use the following template slides as a reference and update the text of the shapes: 
        ```json	
        {template_slides}
        ```
        """

        # Create system prompt to generate the presentation
        system_prompt = """
        You are a PowerPoint presentation generator. 
        You are given a text and a template presentation structure to generate a presentation in JSON format.
        Please output a JSON object containing the following fields: 
        ```json
        {{
            "slide_number": int,
            "shapes": [
                {{
                    "shape_id": int,
                    "shape_type": int,
                    "text": str,
                    "left": float,
                    "top": float,
                    "width": float,
                    "height": float,
                }}
            ]
        }}
        ```
        """

        # Generate new structure of the presentation
        completion_json = self.convert_input_to_json(
            str(parameters.prompt),
            self.__configuration.output_dir,
            prompt,
            system_prompt,
            parameters.use_cache,
        )

        # Add new slides and add shapes
        logger.info(f"-----> Creating new slides to presentation")
        presentation = (
            self.__powerpoint_integration.create_presentation()
        )  # Create empty presentation
        for slide in completion_json.get("completion_json", {}):
            presentation, slide_number = self.__powerpoint_integration.add_slide(
                presentation
            )
            for shape in slide.get("shapes", []):
                self.__powerpoint_integration.add_text_box(
                    presentation=presentation,
                    slide_index=slide_number,
                    left=shape.get("left"),
                    top=shape.get("top"),
                    width=shape.get("width"),
                    height=shape.get("height"),
                    text=shape.get("text"),
                )

        # Save presentation
        return self.save_and_create_asset(
            presentation, completion_json.get("output_dir")
        )

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="powerpoint_generate_slides",
                description=f"Generate a PowerPoint presentation based on a prompt. Slides in presentation {self.__configuration.template_path} will be used as a template.",
                func=lambda **kwargs: self.generate_slides(
                    GenerateSlidesWorkflowParameters(**kwargs)
                ),
                args_schema=GenerateSlidesWorkflowParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass


if __name__ == "__main__":
    from src import secret

    # Initialize naas integration
    naas_integration_config = NaasIntegrationConfiguration(
        api_key=secret.get("NAAS_API_KEY")
    )

    # Initialize powerpoint integration
    powerpoint_integration_config = PowerPointIntegrationConfiguration()

    # Run workflow
    configuration = GenerateSlidesWorkflowConfiguration(
        powerpoint_integration_config=powerpoint_integration_config,
        naas_integration_config=naas_integration_config,
    )
    workflow = GenerateSlidesWorkflow(configuration)
    prompt = (
        "Can you create slides on Palantir Technologies and the future of AI Agents?"
    )
    number_of_slides = 4
    use_cache = True
    output = workflow.generate_slides(
        GenerateSlidesWorkflowParameters(
            prompt=prompt, number_of_slides=number_of_slides, use_cache=use_cache
        )
    )
    logger.info(output)
