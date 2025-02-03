from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from datetime import datetime, date, timedelta
import pandas as pd
import pytz
from abi import logger
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pathlib import Path
import json
import os
import requests
from src import config
from src.workflows.operations_assistant.NaasStorageWorkflows import NaasStorageWorkflows, NaasStorageWorkflowsConfiguration, UploadNaasStorageFileParameters
import hashlib

@dataclass
class PowerPointWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for PowerPoint Workflow.
    
    Attributes:
        powerpoint_integration_config (PowerPointIntegrationConfiguration): PowerPoint integration configuration
        naas_integration_config (NaasIntegrationConfiguration): Naas integration configuration
    """
    powerpoint_integration_config: PowerPointIntegrationConfiguration
    naas_integration_config: NaasIntegrationConfiguration
    template_path: str = Field("assets/PresentationTemplate.pptx", description="Path to the PowerPoint template file")
    output_dir: str = Field("storage/datalake/powerpoint-store", description="Path to save the generated presentation")
    model_id: str = Field("113f2201-9f0e-4bf1-a25f-3ea8ba88e41d", description="Naas model id")
    temperature: float = Field(0.3, description="Temperature for the completion")

class GeneratePresentationFromTextParameters(WorkflowParameters):
    """Parameters for PowerPoint Generate Presentation Workflow execution.
    
    Attributes:
        text (str): Text to generate the presentation
        template_path (str): Path to the PowerPoint template
    """
    text: str = Field(..., description="Text to generate the presentation")
    
class GeneratePresentationFromPromptParameters(WorkflowParameters):
    """Parameters for PowerPoint Generate Presentation Workflow execution.
    
    Attributes:
        prompt (str): Prompt to generate the presentation
        number_of_slides (int): Number of slides to generate
        template_path (str): Path to the PowerPoint template
    """
    prompt: str = Field(..., description="Prompt to generate the presentation")
    number_of_slides: int = Field(..., description="Number of slides to generate")

class PowerPointWorkflow(Workflow):
    """Workflow for generating a PowerPoint presentation based on a prompt."""
    __configuration: PowerPointWorkflowsConfiguration
    
    def __init__(self, configuration: PowerPointWorkflowsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(self.__configuration.powerpoint_integration_config)
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def create_asset(self, file_path: str) -> str:
        """Create or update an asset in storage and return its URL.
        
        Args:
            output_presentation_path (str): Path to the presentation file to upload
            
        Returns:
            str: URL of the created/updated asset
        """
        logger.info(f"-----> Uploading presentation to storage")
        asset = {}
        try:
            # Upload file to storage
            workflow = NaasStorageWorkflows(NaasStorageWorkflowsConfiguration(
                naas_integration_config=self.__configuration.naas_integration_config,
            ))
            workflow.upload_file_from_local(UploadNaasStorageFileParameters(
                workspace_id=config.workspace_id,
                storage_name=config.storage_name,
                local_path=file_path
            ))
            logger.info(f"File uploaded to storage: {file_path}")

            # Create asset
            asset = self.__naas_integration.create_asset(
                workspace_id=config.workspace_id,
                storage_name=config.storage_name,
                object_name=file_path,
                visibility="public"
            )
            if "asset" not in asset:
                asset_id = asset["error"]["message"].split("id:'")[1].split("'")[0]
                asset = self.__naas_integration.get_asset(asset_id)
        except Exception as e:
            logger.error(f"Error creating or updating asset: {e}")
            
        asset_url = asset.get("asset", {}).get("url")
        logger.info(f"Asset URL: {asset_url}")
        return asset_url

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
    ) -> Path:
        """Generate a presentation based on a prompt."""
        # Create hash from prompt to use as unique identifier
        prompt_hash = hashlib.md5(input.encode()).hexdigest()

        # Create directory if it doesn't exist
        output_dir = Path(output_dir) / prompt_hash
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output path
        output_path = output_dir / "presentation"

        if not output_path.with_suffix(".json").exists():
            # Create completion
            logger.info(f"-----> Creating completion")
            completion = self.__naas_integration.create_completion(model_id=self.__configuration.model_id, prompt=prompt, system_prompt=system_prompt, temperature=self.__configuration.temperature)
            with open(output_path.with_suffix(".txt"), "w") as f:
                f.write(completion)
            
            # Save completion to file
            completion_json = self.extract_json_from_completion(completion)
            data = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "model_id": self.__configuration.model_id,
                "temperature": self.__configuration.temperature,
                "completion_text": completion,
                "completion_json": completion_json
            }
            with open(output_path.with_suffix(".json"), "w") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        return output_path
        
    def generate_presentation_from_text(self, parameters: GeneratePresentationFromTextParameters) -> str:
        # Load presentation template
        presentation = self.__powerpoint_integration.create_presentation(self.__configuration.template_path)

        # load slides
        template_slides = self.__powerpoint_integration.list_slides(presentation, text=True)
        shapes = [{"slide_number": slide.get("slide_number"), "shape_id": shape.get("shape_id"), "shape_type": shape.get("shape_type"), "text": shape.get("text")} for slide in template_slides for shape in slide.get("shapes", []) if "template" in shape.get("text", "").lower()]

        """Generate a presentation from a text."""
        prompt = f"""Use the following template slides as a reference: {shapes} and generate a PowerPoint presentation from the following text: 
        ```text
        {parameters.text}
        ```

        Rules:
        - Do NOT create new slides.
        - Use your internal knowledge to update if the initial input text does not have enough information to generate the presentation.
        - Generate all shapes and all slides
        """
        system_prompt = f"""
        You are a PowerPoint presentation generator. 
        You are given a prompt and a template presentation structure.
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
        output_path = self.convert_input_to_json(parameters.text, self.__configuration.output_dir, prompt, system_prompt)
        logger.info(f"-----> Loading completion from file: {output_path.with_suffix('.json')}")
        with open(output_path.with_suffix(".json"), "r") as f:
            completion_json = json.load(f)
        logger.info(f"-----> Completion: {completion_json}")

        logger.info(f"-----> Updating slides in presentation")
        for shape in completion_json.get("completion_json", {}).get("shapes", []):
            self.__powerpoint_integration.update_shape(
                presentation=presentation,
                slide_index=shape.get("slide_number"),
                shape_id=shape.get("shape_id"),
                text=shape.get("new_text"),
            )
        
        # Save presentation
        logger.info(f"-----> Saving presentation to {output_path.with_suffix('.pptx')}")
        self.__powerpoint_integration.save_presentation(presentation, output_path.with_suffix('.pptx'))

        # Create or update asset
        logger.info(f"-----> Uploading presentation to storage")
        asset = self.create_asset(str(output_path.with_suffix('.pptx')))
        return f"Presentation generated and saved to {asset}"

    def generate_presentation_from_prompt(self, parameters: GeneratePresentationFromPromptParameters) -> str:
        # Load presentation template
        presentation = self.__powerpoint_integration.create_presentation(self.__configuration.template_path)

        # load slides
        template_slides = self.__powerpoint_integration.list_slides(presentation, text=True)

        """Generate a presentation from a text."""
        prompt = f"""
        Create {parameters.number_of_slides} slides.
        Use the following template slides as a reference and update the text of the shapes: 
        ```json	
        {template_slides}
        ```
        """
        logger.info(f"-----> Prompt: {prompt}")
        system_prompt = f"""
        You are a PowerPoint presentation generator. 
        You are given a prompt and a template presentation structure.
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
        output_path = self.convert_input_to_json(str(parameters.prompt), self.__configuration.output_dir, prompt, system_prompt)
        logger.info(f"-----> Loading completion from file: {output_path.with_suffix('.json')}")
        with open(output_path.with_suffix(".json"), "r") as f:
            completion_json = json.load(f)

        # Create presentation
        logger.info(f"-----> Creating PowerPoint presentation")
        presentation = self.__powerpoint_integration.create_presentation()

        # Create New Slides
        logger.info(f"-----> Creating new slides to presentation")
        for slide in completion_json.get("completion_json", {}):
            presentation, slide_number = self.__powerpoint_integration.add_slide(presentation)
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
        logger.info(f"-----> Saving presentation to {output_path.with_suffix('.pptx')}")
        self.__powerpoint_integration.save_presentation(presentation, output_path.with_suffix('.pptx'))

        # Create or update asset
        logger.info(f"-----> Uploading presentation to storage")
        asset = self.create_asset(str(output_path.with_suffix('.pptx')))
        return f"Presentation generated and saved to {asset}"

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="generate_powerpoint_presentation_from_text",
                description="Generate a PowerPoint presentation based on a text",
                func=lambda **kwargs: self.generate_presentation_from_text(GeneratePresentationFromTextParameters(**kwargs)),
                args_schema=GeneratePresentationFromTextParameters
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
    template_path = "assets/OrganizationTemplate.pptx"
    configuration = PowerPointWorkflowsConfiguration(
        powerpoint_integration_config=powerpoint_integration_config,
        naas_integration_config=naas_integration_config,
        template_path=template_path,
        output_dir="storage/datalake/powerpoint-store",
        model_id="113f2201-9f0e-4bf1-a25f-3ea8ba88e41d",
        temperature=0.3
    )
    workflow = PowerPointWorkflow(configuration)
    text = """Generate a PowerPoint presentation about Palantir Technologies, a leading software company founded in 2003."""
    workflow.generate_presentation_from_text(GeneratePresentationFromTextParameters(text=text, template_path=template_path))
