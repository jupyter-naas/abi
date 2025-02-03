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

@dataclass
class PowerPointWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for PowerPoint Workflow.
    
    Attributes:
        powerpoint_integration_config (PowerPointIntegrationConfiguration): PowerPoint integration configuration
        naas_integration_config (NaasIntegrationConfiguration): Naas integration configuration
    """
    powerpoint_integration_config: PowerPointIntegrationConfiguration
    naas_integration_config: NaasIntegrationConfiguration

class PowerPointGeneratePresentationParameters(WorkflowParameters):
    """Parameters for PowerPoint Generate Presentation Workflow execution.
    
    Attributes:
        prompt (str): Prompt to generate the presentation
        template_path (str): Path to the PowerPoint template file
        output_path (str): Path to save the generated presentation
    """
    prompt: str = Field(..., description="Prompt to generate the presentation")
    output_path: str = Field(..., description="Path to save the generated presentation")

class PowerPointWorkflow(Workflow):
    """Workflow for generating a PowerPoint presentation based on a prompt."""
    __configuration: PowerPointWorkflowsConfiguration
    
    def __init__(self, configuration: PowerPointWorkflowsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(self.__configuration.powerpoint_integration_config)
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def generate_presentation(self, parameters: PowerPointGeneratePresentationParameters) -> str:
        """Generate a presentation based on a prompt."""
        # Create presentation
        presentation = self.__powerpoint_integration.create_presentation()

        # Create directory if it doesn't exist
        Path(parameters.output_path).parent.mkdir(parents=True, exist_ok=True)

        # Update shapes
        title = "Forvis Mazars Data & AI Services Presentation to Groupe Beneteau"
        subtitle = "Transforming Businesses with Data-Driven Solutions"
        self.__powerpoint_integration.update_shape(presentation, slide_index=0, shape_id=2, text=title)
        self.__powerpoint_integration.update_shape(presentation, slide_index=0, shape_id=3, text=subtitle)

        # Update slide 1
        slide_title_text = "Forvis Mazars Data & AI Services Presentation to Groupe Beneteau"
        slide_subtitle_text = "Transforming Businesses with Data-Driven Solutions"
        self.__powerpoint_integration.update_shape(presentation, slide_index=1, shape_id=2, text=slide_title_text)
        self.__powerpoint_integration.update_shape(presentation, slide_index=1, shape_id=3, text=slide_subtitle_text)

        # Save presentation
        self.__powerpoint_integration.save_presentation(presentation, parameters.output_path)
        
        # Create or update asset
        asset = {}
        try:
            # Upload file to storage
            workflow = NaasStorageWorkflows(NaasStorageWorkflowsConfiguration(
                naas_integration_config=self.__configuration.naas_integration_config,
            ))
            workflow.upload_file_from_local(UploadNaasStorageFileParameters(
                workspace_id=config.workspace_id,
                storage_name=config.storage_name,
                local_path=parameters.output_path
            ))
            logger.info(f"File uploaded to storage: {parameters.output_path}")

            # Create asset
            asset = self.__naas_integration.create_asset(
                workspace_id=config.workspace_id,
                storage_name=config.storage_name,
                object_name=parameters.output_path,
                visibility="public"
            )
            if "asset" not in asset:
                asset_id = asset["error"]["message"].split("id:'")[1].split("'")[0]
                asset = self.__naas_integration.get_asset(asset_id)
        except Exception as e:
            logger.error(f"Error creating or updating asset: {e}")
        asset_url = asset.get("asset").get("url")
        logger.info(f"Asset URL: {asset_url}")
        return f"Presentation generated and saved to {asset_url}"

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="generate_powerpoint_presentation",
                description="Generate a PowerPoint presentation based on a prompt",
                func=lambda **kwargs: self.generate_presentation(PowerPointGeneratePresentationParameters(**kwargs)),
                args_schema=PowerPointGeneratePresentationParameters
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
    powerpoint_integration_config = PowerPointIntegrationConfiguration(
        template_path="assets/PresentationTemplate.pptx"
    )

    # Init workflow
    configuration = PowerPointWorkflowsConfiguration(
        powerpoint_integration_config=powerpoint_integration_config,
        naas_integration_config=naas_integration_config
    )
    workflow = PowerPointWorkflow(configuration)

    # Run workflow
    prompt = "Generate a PowerPoint presentation about the benefits of using AI to improve business operations."
    output_path = "storage/datalake/powerpoint-store/presentation.pptx"
    workflow.generate_presentation(PowerPointGeneratePresentationParameters(prompt=prompt, output_path=output_path))
