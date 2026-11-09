"""Create a presentation from a template and slide contents
(``workflow.create_presentation_from_template_workflow``).

Port of the in-engine workflow (whose tool called a ``run`` it did not define):
duplicate the template slides asked for, fill their text shapes, write the
sources in the notes, save the deck to object storage, upload it to the Naas
workspace storage when Naas credentials are configured (for a download URL),
and add the template and the presentation to the knowledge graph. The module
binds it (``expose_workflow``) with its pipeline and storage.
"""

from __future__ import annotations

import asyncio
import io
import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from naas_abi_apps.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from naas_abi_apps.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    BUNDLED_TEMPLATE,
    AddPowerPointPresentationPipeline,
    AddPowerPointPresentationPipelineParameters,
    read_presentation_bytes,
)
from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import BaseModel, Field
from rdflib import OWL, RDF, Graph

logger = logging.getLogger(__name__)
PPTX = ".pptx"


class ShapeText(BaseModel):
    shape_id: int = Field(
        ..., description="shape_id of a text shape of the template slide"
    )
    text: str = Field(..., description="Text to put in the shape")


class SlideData(BaseModel):
    template_slide_number: int = Field(
        ..., description="Index of the template slide to duplicate"
    )
    shapes: list[ShapeText] = Field(
        default_factory=list, description="Texts of the slide's shapes"
    )
    sources: list[str] = Field(
        default_factory=list, description="Source URLs, written in the slide notes"
    )


class CreatePresentationFromTemplateWorkflowParameters(WorkflowParameters):
    presentation_name: str = Field(
        ..., description="Name of the presentation (without .pptx extension)"
    )
    slides_data: list[SlideData] = Field(..., description="The slides, in order")
    template_path: str | None = Field(
        None,
        description="Template in object storage (prefix/key); default: the module's template",
    )


@dataclass
class CreatePresentationFromTemplateWorkflowConfiguration(WorkflowConfiguration):
    storage: Any = None
    pipeline: AddPowerPointPresentationPipeline | None = None
    template_path: str = BUNDLED_TEMPLATE
    datastore_path: str = "powerpoint/presentations"
    # A NaasIntegration (or None: no upload, no download URL).
    naas: Any = None
    workspace_id: str | None = None
    storage_name: str | None = None


def first_individual(graph: Graph) -> str | None:
    subjects = list(graph.subjects(predicate=RDF.type, object=OWL.NamedIndividual))
    return str(subjects[0]) if subjects else None


class CreatePresentationFromTemplateWorkflow(
    Workflow[CreatePresentationFromTemplateWorkflowParameters]
):
    """Creates a PowerPoint presentation from a template and slide contents (texts
    per shape, sources), stores it, and adds it to the knowledge graph."""

    def __init__(
        self, configuration: CreatePresentationFromTemplateWorkflowConfiguration
    ):
        super().__init__(configuration)
        self.configuration = configuration

    def _build(self, template: bytes, slides: list[SlideData]) -> bytes:
        """The deck, in a thread: python-pptx is synchronous."""
        integration = PowerPointIntegration(
            PowerPointIntegrationConfiguration(template=template)
        )
        template_presentation = deepcopy(integration.create_presentation())
        presentation = integration.remove_all_slides(integration.create_presentation())
        for slide in slides:
            presentation, index = integration.duplicate_slide(
                template_presentation, slide.template_slide_number, presentation
            )
            for shape in slide.shapes:
                try:
                    presentation = integration.update_shape(
                        presentation, index, shape.shape_id, shape.text
                    )
                except Exception as exc:  # noqa: BLE001 - as in-engine: skip the shape
                    logger.error("Shape %s on slide %s: %s", shape.shape_id, index, exc)
            try:
                presentation = integration.update_notes(
                    presentation, index, slide.sources
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Notes on slide %s: %s", index, exc)
        stream = io.BytesIO()
        presentation.save(stream)
        return stream.getvalue()

    async def run(
        self, parameters: CreatePresentationFromTemplateWorkflowParameters
    ) -> dict[str, Any]:
        configuration = self.configuration
        name = parameters.presentation_name
        if not name.endswith(PPTX):
            name += PPTX
        template_path = parameters.template_path or configuration.template_path
        template = await read_presentation_bytes(configuration.storage, template_path)

        content = await asyncio.to_thread(self._build, template, parameters.slides_data)
        await configuration.storage.put_object(
            configuration.datastore_path, name, content
        )
        storage_path = f"{configuration.datastore_path}/{name}"

        download_url = None
        if configuration.naas is not None:
            asset = await configuration.naas.upload_asset(
                data=content,
                workspace_id=configuration.workspace_id,
                storage_name=configuration.storage_name,
                prefix="assets",
                object_name=name,
                visibility="public",
                return_url=True,
            )
            download_url = asset.get("asset_url")

        template_uri = None
        presentation_uri = None
        if configuration.pipeline is not None:
            template_uri = first_individual(
                await configuration.pipeline.run(
                    AddPowerPointPresentationPipelineParameters(
                        presentation_name=template_path.split("/")[-1].split(":")[-1],
                        storage_path=template_path,
                    )
                )
            )
            presentation_uri = first_individual(
                await configuration.pipeline.run(
                    AddPowerPointPresentationPipelineParameters(
                        presentation_name=name,
                        storage_path=storage_path,
                        download_url=download_url,
                        template_uri=template_uri,
                    )
                )
            )
        return {
            "presentation_name": name,
            "storage_path": storage_path,
            "download_url": download_url,
            "presentation_uri": presentation_uri,
            "template_uri": template_uri,
        }
