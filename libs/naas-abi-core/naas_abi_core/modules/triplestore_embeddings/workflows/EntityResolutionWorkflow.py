from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict

from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from naas_abi_core import logger
from naas_abi_core.modules.triplestore_embeddings.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipeline,
    MergeIndividualsPipelineConfiguration,
    MergeIndividualsPipelineParameters,
)
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
from naas_abi_core.modules.triplestore_embeddings.utils.Triples import TriplesUtils
from naas_abi_core.modules.triplestore_embeddings.workflows.CreateTripleEmbeddingsWorkflow import (
    CreateTripleEmbeddingsWorkflow,
    CreateTripleEmbeddingsWorkflowConfiguration,
    CreateTripleEmbeddingsWorkflowParameters,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field
from rdflib import RDFS, Graph, Literal, URIRef


@dataclass
class EntityResolutionWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for EntityResolutionWorkflow.

    merge_pipeline_configuration: MergeIndividualsPipelineConfiguration
    create_embeddings_workflow_configuration: (
        CreateTripleEmbeddingsWorkflowConfiguration
    )
    vector_store: VectorStoreService
    triple_store: TripleStoreService
    embeddings_model: Embeddings
    embeddings_dimension: int
    collection_name: str = "triple_embeddings"
    """

    merge_pipeline_configuration: MergeIndividualsPipelineConfiguration
    create_embeddings_workflow_configuration: (
        CreateTripleEmbeddingsWorkflowConfiguration
    )
    vector_store: VectorStoreService
    triple_store: TripleStoreService
    embeddings_model: Embeddings
    embeddings_dimension: int
    collection_name: str = "triple_embeddings"


class EntityResolutionWorkflowParameters(WorkflowParameters):
    """Parameters for CreateTripleEmbeddings workflow execution.

    Attributes:
        s: The subject of the triple
        p: The predicate of the triple
        o: The object of the triple
    """

    model_config = {
        "arbitrary_types_allowed": True,
    }

    s: Annotated[URIRef | str, Field(..., description="The subject of the triple")]
    p: Annotated[
        URIRef | str, Field(..., description="The predicate of the triple")
    ] = RDFS.label
    o: Annotated[Literal | str, Field(..., description="The object of the triple")]
    similarity_threshold: Annotated[
        float,
        Field(
            ge=0.95,
            le=1.0,
            description="Minimum similarity score (0.95-1.0) to consider entities as duplicates.",
        ),
    ] = 0.98


class EntityResolutionWorkflow(Workflow):
    """Workflow for resolving entities in a given class."""

    __configuration: EntityResolutionWorkflowConfiguration
    __embeddings_utils: EmbeddingsUtils
    __triples_utils: TriplesUtils

    def __init__(self, configuration: EntityResolutionWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        # Init pipelines
        self.__merge_pipeline = MergeIndividualsPipeline(
            self.__configuration.merge_pipeline_configuration
        )
        self.__create_embeddings_workflow = CreateTripleEmbeddingsWorkflow(
            self.__configuration.create_embeddings_workflow_configuration
        )

        # Get services from configuration
        self.__triple_store_service = self.__configuration.triple_store
        self.__vector_store_service = self.__configuration.vector_store
        self.__embeddings_model = self.__configuration.embeddings_model
        self.__collection_name = self.__configuration.collection_name

        # Init utils
        self.__embeddings_utils = EmbeddingsUtils(
            embeddings_model=self.__embeddings_model
        )
        self.__triples_utils = TriplesUtils(triple_store=self.__triple_store_service)

    def resolve_entity(
        self, parameters: EntityResolutionWorkflowParameters
    ) -> Dict[str, Any] | Graph:
        """Create embeddings for a given triple and store them in a vector store.

        Args:
            parameters: The workflow parameters containing s, p, and o.

        Returns:
            A dictionary containing the number of entities processed and collection information
        """
        logger.info(
            f"Checking if entity resolution is needed for triple '{parameters.s} {parameters.p} {parameters.o}'..."
        )
        # Init
        uri = str(parameters.s)
        label = str(parameters.o)
        metadata: Dict[str, Any] = {"uri": uri, "label": label}

        # Get RDF types from subject
        rdf_types = self.__triples_utils.get_rdf_type_from_subject(parameters.s)
        if len(rdf_types) == 0:
            logger.error(f"No RDF types found for {parameters.s}")
            return {
                "status": "error",
                "message": f"No RDF types found for {parameters.s}",
            }

        # Add RDF types to metadata
        metadata = self.__triples_utils.add_rdf_types_to_metadata(metadata, rdf_types)
        type_uris = metadata.get("type_uri", [])
        owl_types = metadata.get("owl_type", [])

        # Check if entity resolution is needed
        # Logic: if type_uris are GDC or SDC then entity resolution must be performed with labels
        gdc_sdc_class_uris = [
            "http://purl.obolibrary.org/obo/BFO_0000031",
            "http://purl.obolibrary.org/obo/BFO_0000020",
        ]
        is_gdc_sdc_class = False
        type_uri_index = 0
        while type_uri_index < len(type_uris):
            type_uri = type_uris[type_uri_index]
            is_gdc_sdc_class = self.__triples_utils.is_subclass_of(
                type_uri, gdc_sdc_class_uris
            )
            if is_gdc_sdc_class is False:
                break
            type_uri_index += 1

        if is_gdc_sdc_class:
            logger.info(
                f"Entity '{label}' ({uri}) is a GDC or SDC class, searching for similar entities in the vector store..."
            )
            # Search for similar entities in the vector store
            vector = self.__embeddings_utils.create_vector_embedding(label)
            search_results = self.__vector_store_service.search_similar(
                collection_name=self.__collection_name,
                query_vector=vector,
                k=5,
                filter={
                    "owl_type": owl_types,
                    "type_uri": type_uris,
                },
                include_metadata=True,
            )
            logger.debug(f"Search results: {search_results}")
            for search_result in search_results:
                if search_result.score >= parameters.similarity_threshold:
                    logger.info(
                        f"Found similar entity '{label}' (score: {search_result.score}). Matched entities: {search_result.metadata}'"
                    )
                    if (
                        search_result.metadata is not None
                        and search_result.metadata.get("uri") is not None
                    ):
                        uri_value = search_result.metadata.get("uri")
                        if isinstance(uri_value, str):
                            return self.__merge_pipeline.run(
                                MergeIndividualsPipelineParameters(
                                    merge_pairs=[(uri_value, uri)]
                                )
                            )
                        else:
                            logger.warning(
                                f"Similar entity '{label}' (score: {search_result.score}) has non-string URI: {uri_value}"
                            )
                            continue
                    else:
                        logger.warning(
                            f"Similar entity '{label}' (score: {search_result.score}) has no metadata or URI"
                        )
                        continue

        # No similar entities found, use CreateTripleEmbeddingsWorkflow
        logger.info(
            "No similar entities found, creating triple embeddings for new entity"
        )
        return self.__create_embeddings_workflow.create_triple_embeddings(
            CreateTripleEmbeddingsWorkflowParameters(
                s=parameters.s,
                p=parameters.p,
                o=parameters.o,
            )
        )

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return []

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        pass
