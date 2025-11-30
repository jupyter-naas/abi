import os
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi.utils.SPARQL import get_identifier, get_subject_graph
from naas_abi.utils.Storage import get_powerpoint_presentation
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Graph import URI_REGEX
from naas_abi_core.utils.String import create_hash_from_string
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from pptx import Presentation
from pydantic import Field
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef


@dataclass
class AddPowerPointPresentationPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddPowerPointPresentationPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    powerpoint_configuration: PowerPointIntegrationConfiguration
    triple_store: ITripleStoreService


class AddPowerPointPresentationPipelineParameters(PipelineParameters):
    presentation_name: Annotated[
        str,
        Field(
            description="Name of the presentation",
        ),
    ]
    storage_path: Annotated[
        str,
        Field(
            description="Storage path for the presentation",
        ),
    ]
    download_url: Optional[
        Annotated[
            str,
            Field(
                description="Download URL for the presentation",
            ),
        ]
    ] = None
    template_uri: Optional[
        Annotated[
            str,
            Field(
                description="URI of the template",
                pattern=URI_REGEX,
            ),
        ]
    ] = None


class AddPowerPointPresentationPipeline(Pipeline):
    """Pipeline for adding a presentation to the ontology."""

    __configuration: AddPowerPointPresentationPipelineConfiguration

    def __init__(self, configuration: AddPowerPointPresentationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__powerpoint_integration = PowerPointIntegration(
            configuration.powerpoint_configuration
        )

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AddPowerPointPresentationPipelineParameters):
            raise ValueError(
                "Parameters must be of type AddPowerPointPresentationPipelineParameters"
            )

        # Get all shapes and slides from presentation
        if parameters.storage_path.startswith("src"):
            presentation = self.__powerpoint_integration.create_presentation(
                parameters.storage_path
            )
        else:
            presentation = Presentation(
                get_powerpoint_presentation(
                    os.path.dirname(parameters.storage_path),
                    os.path.basename(parameters.storage_path),
                )
            )

        # Get core properties from presentation
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
        except Exception as e:
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
        presentation_uri = get_identifier(presentation_hash, type=ABI.unique_id)
        if presentation_uri is not None:
            logger.info(f"🛑 Presentation already exists: {presentation_uri}")
            return get_subject_graph(presentation_uri, depth=2)

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
        shapes_and_slides = self.__powerpoint_integration.get_all_shapes_and_slides(
            presentation
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

        # Save the graph
        if len(graph) > 0:
            logger.info(f"✅ Inserting {len(graph)} triples into the triple store")
            self.__configuration.triple_store.insert(graph)
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="add_powerpoint_presentation",
                description="Adds a PowerPoint presentation to the triple store.",
                func=lambda **kwargs: self.run(
                    AddPowerPointPresentationPipelineParameters(**kwargs)
                ),
                args_schema=AddPowerPointPresentationPipelineParameters,
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
