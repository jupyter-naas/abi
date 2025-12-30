import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core import logger
from naas_abi_marketplace.applications.powerpoint import ABIModule
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipeline,
    AddPowerPointPresentationPipelineConfiguration,
    AddPowerPointPresentationPipelineParameters,
)
from pydantic import Field
from rdflib import OWL, RDF


@dataclass
class CreatePresentationFromTemplateWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreatePresentationFromTemplateWorkflow.

    Attributes:
        powerpoint_configuration (PowerPointIntegrationConfiguration): Configuration for the PowerPoint integration
        naas_configuration (NaasIntegrationConfiguration): Configuration for the Naas integration
        pipeline_configuration (AddPowerPointPresentationPipelineConfiguration): Configuration for the AddPowerPointPresentationPipeline
        datastore_path (str): Path to the datastore
    """

    triple_store: ITripleStoreService
    powerpoint_configuration: PowerPointIntegrationConfiguration
    naas_configuration: NaasIntegrationConfiguration
    pipeline_configuration: AddPowerPointPresentationPipelineConfiguration
    datastore_path: str = "datastore/powerpoint/presentations"
    workspace_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.workspace_id)
    storage_name: str = field(default_factory=lambda: ABIModule.get_instance().configuration.storage_name)


class CreatePresentationFromTemplateWorkflowParameters(WorkflowParameters):
    """Parameters for CreatePresentationTemplateWorkflow execution.

    Attributes:
        presentation_name (str): Name of the presentation (without .pptx extension)
        slides_data (List[Dict]): List of slide data dictionaries, each containing:
            - slide_number (int): Index of the slide
            - template_slide_number (int): Index of the template slide to duplicate
            - shapes (List[Dict]): List of shape dictionaries with shape_id and text
            - sources (List[str]): List of source URLs for the slide
        template_path (str): Path to the PowerPoint template file
    """

    presentation_name: str = Field(
        ..., description="Name of the presentation (without .pptx extension)"
    )
    slides_data: List[Dict] = Field(..., description="List of slide data dictionaries")
    template_path: str = Field(..., description="Path to the PowerPoint template file")


class CreatePresentationFromTemplateWorkflow(Workflow):
    __configuration: CreatePresentationFromTemplateWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(
        self, configuration: CreatePresentationFromTemplateWorkflowConfiguration
    ):
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(
            self.__configuration.powerpoint_configuration
        )
        self.__naas_integration = NaasIntegration(
            self.__configuration.naas_configuration
        )
        self.__powerpoint_pipeline = AddPowerPointPresentationPipeline(
            AddPowerPointPresentationPipelineConfiguration(
                powerpoint_configuration=self.__configuration.powerpoint_configuration,
                triple_store=self.__configuration.triple_store,
            )
        )
        self.__storage_utils = StorageUtils(ABIModule.get_instance().engine.services.object_storage)

    def create_presentation(
        self, parameters: CreatePresentationFromTemplateWorkflowParameters
    ) -> Dict[str, Any]:
        """Create a presentation from JSON data.

        Args:
            parameters: Workflow parameters containing presentation_name, slides_data, and template_path

        Returns:
            Dict containing:
                - presentation_name (str): Name of the presentation
                - storage_path (str): Path where the presentation is stored
                - download_url (str): Public download URL from Naas
        """
        logger.debug(
            f"📊 Creating presentation '{parameters.presentation_name}' from JSON"
        )

        # Ensure presentation name ends with .pptx
        presentation_name = parameters.presentation_name
        if not presentation_name.endswith(".pptx"):
            presentation_name = presentation_name + ".pptx"

        # Create presentation from template
        template_presentation = deepcopy(
            self.__powerpoint_integration.create_presentation(parameters.template_path)
        )
        presentation = self.__powerpoint_integration.create_presentation(
            parameters.template_path
        )

        # Clear existing slides and create new ones based on template
        logger.debug("🧹 Clearing existing slides from presentation")
        presentation = self.__powerpoint_integration.remove_all_slides(presentation)

        # Create slides based on the data
        logger.debug("📝 Processing slides")
        for slide_data in parameters.slides_data:
            # Duplicate template slide
            template_slide_number = slide_data.get("template_slide_number")
            if template_slide_number is None:
                logger.error(
                    f"❌ Template slide number not found for slide:\n {json.dumps(slide_data, indent=4)}"
                )
                continue

            presentation, new_slide_idx = self.__powerpoint_integration.duplicate_slide(
                template_presentation, template_slide_number, presentation
            )

            # Add shapes to slide
            shapes = slide_data.get("shapes", [])
            for shape in shapes:
                shape_id = shape.get("shape_id")
                text = shape.get("text")
                try:
                    presentation = self.__powerpoint_integration.update_shape(
                        presentation, new_slide_idx, shape_id, text
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Failed to update shape {shape_id} on slide {new_slide_idx}: {str(e)}"
                    )
                    continue

            # Update notes with sources
            sources = slide_data.get("sources", [])
            try:
                presentation = self.__powerpoint_integration.update_notes(
                    presentation, new_slide_idx, sources
                )
            except Exception as e:
                logger.error(
                    f"❌ Failed to update notes on slide {new_slide_idx}: {str(e)}"
                )
                continue

        # Save presentation to storage
        self.__storage_utils.save_powerpoint_presentation(
            presentation,
            self.__configuration.datastore_path,
            presentation_name,
            copy=False,
        )
        storage_path = os.path.join(
            self.__configuration.datastore_path, presentation_name
        )

        # Save presentation to byte stream
        byte_stream = BytesIO()
        presentation.save(byte_stream)
        byte_stream.seek(0)

        # Create asset in Naas
        asset = self.__naas_integration.upload_asset(
            data=byte_stream.getvalue(),
            workspace_id=self.__configuration.workspace_id,
            storage_name=self.__configuration.storage_name,
            prefix="assets",
            object_name=presentation_name,
            visibility="public",
            return_url=True,
        )
        download_url = asset.get("asset_url")

        # Add presentation to triple store
        template_graph = self.__powerpoint_pipeline.run(
            AddPowerPointPresentationPipelineParameters(
                presentation_name=os.path.basename(parameters.template_path),
                storage_path=parameters.template_path,
            )
        )
        template_subjects = list(
            template_graph.subjects(predicate=RDF.type, object=OWL.NamedIndividual)
        )
        template_uri = str(template_subjects[0]) if len(template_subjects) > 0 else None
        logger.debug(f"🧩 Template presentation URI: {template_uri}")

        presentation_graph = self.__powerpoint_pipeline.run(
            AddPowerPointPresentationPipelineParameters(
                presentation_name=presentation_name,
                storage_path=os.path.join(
                    self.__configuration.datastore_path, presentation_name
                ),
                download_url=download_url,
                template_uri=template_uri,
            )
        )
        presentation_subjects = list(
            presentation_graph.subjects(predicate=RDF.type, object=OWL.NamedIndividual)
        )
        presentation_uri = (
            str(presentation_subjects[0]) if len(presentation_subjects) > 0 else None
        )
        logger.debug(f"📽️  Presentation URI: {presentation_uri}")

        return {
            "presentation_name": presentation_name,
            "storage_path": storage_path,
            "download_url": download_url,
            "presentation_uri": presentation_uri,
            "template_uri": template_uri,
        }

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="create_presentation_from_template",
                description="Creates a PowerPoint presentation from templates and corresponding JSON data with slides, shapes, and sources",
                func=lambda **kwargs: self.run(
                    CreatePresentationFromTemplateWorkflowParameters(**kwargs)
                ),
                args_schema=CreatePresentationFromTemplateWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
