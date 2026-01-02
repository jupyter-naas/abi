from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi import ABIModule
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.Graph import URI_REGEX
from naas_abi_core.utils.SPARQL import SPARQLUtils
from pydantic import Field
from rdflib import RDFS, SKOS, XSD, Graph, Literal, URIRef


@dataclass
class UpdateDataPropertyPipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdateDataPropertyPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService


class UpdateDataPropertyPipelineParameters(PipelineParameters):
    subject_uri: Annotated[str, Field(description="Subject URI", pattern=URI_REGEX)]
    predicate_uri: Annotated[
        str, Field(description="Predicate URI", pattern=r"^http.+$")
    ]
    object_new_value: Annotated[
        str,
        Field(
            description="New value for the object",
        ),
    ]
    language: Optional[
        Annotated[
            Optional[str],
            Field(
                description="Language of the object",
            ),
        ]
    ] = None


class UpdateDataPropertyPipeline(Pipeline):
    """Pipeline for updating a data property in the ontology."""

    __configuration: UpdateDataPropertyPipelineConfiguration

    def __init__(self, configuration: UpdateDataPropertyPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__sparql_utils = SPARQLUtils(
            ABIModule.get_instance().engine.services.triple_store
        )

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateDataPropertyPipelineParameters):
            raise ValueError(
                "Parameters must be of type UpdateDataPropertyPipelineParameters"
            )

        graph_insert = Graph()
        graph_remove = Graph()
        subject_uri = URIRef(parameters.subject_uri)
        predicate_uri = URIRef(parameters.predicate_uri)
        logger.info(
            f"Updating subject '{subject_uri}' with predicate '{predicate_uri}' and value '{parameters.object_new_value}'"
        )

        if isinstance(parameters.object_new_value, str):
            if parameters.language is not None:
                object_new_value = Literal(
                    parameters.object_new_value, lang=parameters.language
                )
            else:
                object_new_value = Literal(parameters.object_new_value)
        elif isinstance(parameters.object_new_value, float):
            object_new_value = Literal(parameters.object_new_value, datatype=XSD.float)
        elif isinstance(parameters.object_new_value, int):
            object_new_value = Literal(
                parameters.object_new_value, datatype=XSD.integer
            )
        else:
            logger.error(f"Invalid object new value: {parameters.object_new_value}")
            return Graph()

        graph = self.__sparql_utils.get_subject_graph(parameters.subject_uri)
        check_object_property = list(graph.triples((subject_uri, predicate_uri, None)))
        logger.info(f"Check object property: {len(check_object_property)}")
        if len(check_object_property) == 0:
            logger.error(
                f"Property {parameters.predicate_uri} not found for subject {parameters.subject_uri}"
            )
            return Graph()
        elif len(check_object_property) == 1 and predicate_uri != RDFS.label:
            property_value = graph.value(subject_uri, predicate_uri)
            if property_value:
                graph_remove.add((subject_uri, predicate_uri, property_value))
            graph_insert.add((subject_uri, predicate_uri, object_new_value))
        elif len(check_object_property) == 1 and predicate_uri == RDFS.label:
            property_value = graph.value(subject_uri, predicate_uri)
            if property_value:
                graph_remove.add((subject_uri, predicate_uri, property_value))
            graph_insert.add((subject_uri, predicate_uri, object_new_value))
            graph_insert.add((subject_uri, SKOS.altLabel, object_new_value))
        else:
            logger.error(
                f"Multiple values found for property {parameters.predicate_uri} for subject {parameters.subject_uri}"
            )
            return Graph()

        # Save to triplestore
        if len(graph_insert) > 0:
            logger.info("✅ Inserting data to triplestore:")
            logger.info(graph_insert.serialize(format="turtle"))
            self.__configuration.triple_store.insert(graph_insert)
        if len(graph_remove) > 0:
            logger.info("✅ Removing data from triplestore:")
            logger.info(graph_remove.serialize(format="turtle"))
            self.__configuration.triple_store.remove(graph_remove)
        return self.__sparql_utils.get_subject_graph(parameters.subject_uri)

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_data_property",
                description="Update a data property in the ontology",
                func=lambda **kwargs: self.run(
                    UpdateDataPropertyPipelineParameters(**kwargs)
                ),
                args_schema=UpdateDataPropertyPipelineParameters,
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


if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])
    triple_store_service = engine.services.triple_store

    subject_uri = "http://ontology.naas.ai/abi/1b765700-9fa1-4e1d-9496-108445aafb34"
    predicate_uri = str(RDFS.label)
    object_new_value = "Ford Motor Company"
    language = "en"

    configuration = UpdateDataPropertyPipelineConfiguration(
        triple_store=triple_store_service
    )

    pipeline = UpdateDataPropertyPipeline(configuration)
    graph = pipeline.run(
        UpdateDataPropertyPipelineParameters(
            subject_uri=subject_uri,
            predicate_uri=predicate_uri,
            object_new_value=object_new_value,
            language=language,
        )
    )
    logger.info(graph.serialize(format="turtle"))
