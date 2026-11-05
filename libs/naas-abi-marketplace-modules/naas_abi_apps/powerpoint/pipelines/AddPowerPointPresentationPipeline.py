"""Add a PowerPoint presentation (slides, shapes, properties) to the knowledge
graph (``pipeline.add_power_point_presentation_pipeline``).

Port of the in-engine pipeline: the same graph. The file is read from object
storage, or is the bundled template (``BUNDLED_TEMPLATE``); the graph goes to
the module's named graph. A presentation already in the graph (same
properties) is returned as stored, not added again.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from naas_abi_apps.common.graph import rows, sparql_string
from naas_abi_apps.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from naas_abi_sdk.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from pptx import Presentation
from pydantic import Field
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

logger = logging.getLogger(__name__)

URI_REGEX = r"http:\/\/ontology\.naas\.ai\/.+\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
# A storage path naming a template shipped in the package, not an object.
BUNDLED_PREFIX = "bundled:"
BUNDLED_TEMPLATE = f"{BUNDLED_PREFIX}TemplateMinimal.pptx"


def create_hash_from_string(input_string: str) -> str:
    """sha256 hex digest, as ``naas_abi_core.utils.String.create_hash_from_string``."""
    return hashlib.sha256(input_string.encode()).hexdigest()


async def read_presentation_bytes(storage: Any, storage_path: str) -> bytes:
    """A bundled template, or an object of the engine's object storage."""
    if storage_path.startswith(BUNDLED_PREFIX):
        return (TEMPLATES_DIR / storage_path[len(BUNDLED_PREFIX) :]).read_bytes()
    return await storage.get_object(
        os.path.dirname(storage_path), os.path.basename(storage_path)
    )


@dataclass
class AddPowerPointPresentationPipelineConfiguration(PipelineConfiguration):
    triple_store: Any = None
    storage: Any = None
    graph_name: str = "http://ontology.naas.ai/graph/default"
    powerpoint_configuration: PowerPointIntegrationConfiguration = field(
        default_factory=PowerPointIntegrationConfiguration
    )


class AddPowerPointPresentationPipelineParameters(PipelineParameters):
    presentation_name: str = Field(..., description="Name of the presentation")
    storage_path: str = Field(
        ..., description="Storage path for the presentation (prefix/key)"
    )
    download_url: str | None = Field(
        None, description="Download URL for the presentation"
    )
    template_uri: str | None = Field(
        None, description="URI of the template", pattern=URI_REGEX
    )


class AddPowerPointPresentationPipeline(
    Pipeline[AddPowerPointPresentationPipelineParameters]
):
    """Adds a PowerPoint presentation (slides, shapes, author, dates) to the knowledge graph."""

    def __init__(self, configuration: AddPowerPointPresentationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(
            configuration.powerpoint_configuration
        )

    @classmethod
    def New(cls, module: Any) -> AddPowerPointPresentationPipeline:
        services = module.engine.services
        return cls(
            AddPowerPointPresentationPipelineConfiguration(
                triple_store=services.triple_store,
                storage=services.object_storage,
                graph_name=module.configuration.graph_name,
            )
        )

    async def _identifier(self, identifier: str) -> URIRef | None:
        """As core's ``SPARQLUtils.get_identifier`` on ``abi:unique_id``."""
        found = rows(
            await self.__configuration.triple_store.query(
                f"SELECT ?s WHERE {{ ?s <http://ontology.naas.ai/abi/unique_id> {sparql_string(identifier)} . }} LIMIT 1"
            )
        )
        return URIRef(found[0]["s"]) if found else None

    async def run(
        self, parameters: AddPowerPointPresentationPipelineParameters
    ) -> Graph:
        content = await read_presentation_bytes(
            self.__configuration.storage, parameters.storage_path
        )
        presentation = Presentation(io.BytesIO(content))

        author = None
        created_date = None
        modified_date = None
        last_modified_by = None
        try:
            core_props = presentation.core_properties

            # Combine multiple properties to create a unique signature
            signature_parts = [parameters.presentation_name]
            if hasattr(core_props, "author") and core_props.author:
                author = core_props.author
                logger.info(f"✅ Author: {author}")
                signature_parts.append(author)
            if hasattr(core_props, "created") and core_props.created:
                created_date = core_props.created.strftime("%Y-%m-%dT%H:%M:%S%z")
                logger.info(f"✅ Created date: {created_date}")
                signature_parts.append(created_date)
            if hasattr(core_props, "modified") and core_props.modified:
                modified_date = core_props.modified.strftime("%Y-%m-%dT%H:%M:%S%z")
                logger.info(f"✅ Modified date: {modified_date}")
                signature_parts.append(modified_date)
            if hasattr(core_props, "last_modified_by") and core_props.last_modified_by:
                last_modified_by = core_props.last_modified_by
                logger.info(f"✅ Last modified by: {last_modified_by}")
                signature_parts.append(last_modified_by)

            identifier = "_".join(signature_parts)
            logger.info(
                f"✅ Generated signature from document properties: {identifier}"
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"❌ Failed to get core properties from presentation: {e}")
            return Graph()

        # Initialize graphs
        ABI = Namespace("http://ontology.naas.ai/abi/")
        PPT = Namespace("http://ontology.naas.ai/abi/powerpoint/")

        graph = Graph()
        graph.bind("rdfs", RDFS)
        graph.bind("rdf", RDF)
        graph.bind("owl", OWL)
        graph.bind("abi", ABI)
        graph.bind("ppt", PPT)
        class_presentation = PPT.Presentation
        class_slide = PPT.Slide
        class_shape = PPT.Shape

        # Add objects if not exists
        presentation_hash = create_hash_from_string(identifier)
        presentation_uri = await self._identifier(presentation_hash)
        if presentation_uri is not None:
            logger.info(f"🛑 Presentation already exists: {presentation_uri}")
            return await self.__configuration.triple_store.get_subject_graph(
                str(presentation_uri)
            )

        presentation_uri = ABI[str(uuid.uuid4())]
        graph.add((presentation_uri, RDF.type, OWL.NamedIndividual))
        graph.add((presentation_uri, RDF.type, class_presentation))
        graph.add((presentation_uri, RDFS.label, Literal(parameters.presentation_name)))
        graph.add((presentation_uri, ABI.unique_id, Literal(presentation_hash)))
        graph.add(
            (presentation_uri, PPT.storage_path, Literal(parameters.storage_path))
        )
        if author is not None:
            graph.add((presentation_uri, PPT.author, Literal(author)))
        if created_date is not None:
            graph.add(
                (
                    presentation_uri,
                    PPT.created_date,
                    Literal(created_date, datatype=XSD.dateTime),
                )
            )
        if last_modified_by is not None:
            graph.add(
                (presentation_uri, PPT.last_modified_by, Literal(last_modified_by))
            )
        if modified_date is not None:
            graph.add(
                (
                    presentation_uri,
                    PPT.modified_date,
                    Literal(modified_date, datatype=XSD.dateTime),
                )
            )
        if parameters.download_url is not None:
            graph.add(
                (presentation_uri, PPT.download_url, Literal(parameters.download_url))
            )
        if parameters.template_uri is not None:
            graph.add(
                (presentation_uri, PPT.hasTemplate, URIRef(parameters.template_uri))
            )
            graph.add(
                (URIRef(parameters.template_uri), PPT.isTemplateOf, presentation_uri)
            )

        # Add shapes and slides to graph
        shapes_and_slides = await asyncio.to_thread(
            self.__powerpoint_integration.get_all_shapes_and_slides, presentation
        )
        for shape_and_slide in shapes_and_slides:
            slide_number = shape_and_slide.get("slide_number")
            shapes = shape_and_slide.get("shapes", [])
            slide_uri = ABI[str(uuid.uuid4())]
            graph.add((slide_uri, RDF.type, OWL.NamedIndividual))
            graph.add((slide_uri, RDF.type, class_slide))
            graph.add(
                (
                    slide_uri,
                    PPT.slide_number,
                    Literal(slide_number, datatype=XSD.integer),
                )
            )
            graph.add((presentation_uri, PPT.hasSlide, slide_uri))
            graph.add((slide_uri, PPT.isSlideOf, presentation_uri))
            for shape in shapes:
                shape_id = shape.get("shape_id", 0)
                shape_type = shape.get("shape_type", 0)
                shape_text = shape.get("text", "")
                shape_alt_text = shape.get("shape_alt_text", "")
                shape_position_left = shape.get("left", 0)
                shape_position_top = shape.get("top", 0)
                shape_size_width = shape.get("width", 0)
                shape_size_height = shape.get("height", 0)
                shape_rotation = shape.get("rotation", 0)
                shape_uri = ABI[str(uuid.uuid4())]
                graph.add((shape_uri, RDF.type, OWL.NamedIndividual))
                graph.add((shape_uri, RDF.type, class_shape))
                graph.add(
                    (shape_uri, PPT.shape_id, Literal(shape_id, datatype=XSD.integer))
                )
                graph.add(
                    (
                        shape_uri,
                        PPT.shape_type,
                        Literal(shape_type, datatype=XSD.integer),
                    )
                )
                graph.add((shape_uri, PPT.shape_alt_text, Literal(shape_alt_text)))
                graph.add((shape_uri, PPT.shape_text, Literal(shape_text)))
                graph.add(
                    (
                        shape_uri,
                        PPT.shape_position_left,
                        Literal(shape_position_left, datatype=XSD.decimal),
                    )
                )
                graph.add(
                    (
                        shape_uri,
                        PPT.shape_position_top,
                        Literal(shape_position_top, datatype=XSD.decimal),
                    )
                )
                graph.add(
                    (
                        shape_uri,
                        PPT.shape_size_width,
                        Literal(shape_size_width, datatype=XSD.decimal),
                    )
                )
                graph.add(
                    (
                        shape_uri,
                        PPT.shape_size_height,
                        Literal(shape_size_height, datatype=XSD.decimal),
                    )
                )
                graph.add(
                    (
                        shape_uri,
                        PPT.shape_rotation_angle,
                        Literal(shape_rotation, datatype=XSD.decimal),
                    )
                )
                graph.add((shape_uri, PPT.isShapeOf, slide_uri))
                graph.add((slide_uri, PPT.hasShape, shape_uri))

        if len(graph) > 0:
            logger.info(f"✅ Inserting {len(graph)} triples into the triple store")
            await self.__configuration.triple_store.insert(
                graph, URIRef(self.__configuration.graph_name)
            )
        return graph
