from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict

from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from naas_abi_core import logger
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field
from rdflib import RDFS, Literal, URIRef


@dataclass
class DeleteTripleEmbeddingsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateTripleEmbeddings workflow.

    vector_store: VectorStoreService
    collection_name: str = "triple_embeddings"
    """

    vector_store: VectorStoreService
    embeddings_model: Embeddings
    embeddings_dimension: int
    collection_name: str = "triple_embeddings"


class DeleteTripleEmbeddingsWorkflowParameters(WorkflowParameters):
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


class DeleteTripleEmbeddingsWorkflow(Workflow):
    """Workflow for creating embeddings for named individuals of a given class and storing them in a vector store."""

    __configuration: DeleteTripleEmbeddingsWorkflowConfiguration
    __embeddings_utils: EmbeddingsUtils

    def __init__(self, configuration: DeleteTripleEmbeddingsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        # Get services from configuration
        self.__vector_store_service = self.__configuration.vector_store
        self.__embeddings_model = self.__configuration.embeddings_model
        self.__embeddings_dimension = self.__configuration.embeddings_dimension
        self.__collection_name = self.__configuration.collection_name

        # Init embeddings utils
        self.__embeddings_utils = EmbeddingsUtils(
            embeddings_model=self.__embeddings_model
        )

    def delete_triple_embeddings(
        self, parameters: DeleteTripleEmbeddingsWorkflowParameters
    ) -> Dict[str, Any]:
        """Delete embeddings for a given triple from a vector store.

        Args:
            parameters: The workflow parameters containing s, p, and o.

        Returns:
            A dictionary containing the number of entities processed and collection information
        """
        # Init
        uri = str(parameters.s)
        uuid_id = EmbeddingsUtils.create_uuid_from_string(uri)
        label = str(parameters.o)

        # Ensure collection exists
        self.__vector_store_service.ensure_collection(
            collection_name=self.__collection_name,
            dimension=self.__embeddings_dimension,
            distance_metric="cosine",
        )

        # Check if embeddings already exist for this UUID filtered by uri
        vector = self.__embeddings_utils.create_vector_embedding(label)
        search_results = self.__vector_store_service.search_similar(
            collection_name=self.__collection_name,
            query_vector=vector,
            k=10,
            filter={"uri": uri},
            include_metadata=True,
        )
        # If embeddings found, delete it
        if len(search_results) > 0:
            message = f"Deleting embeddings for '{uri}' in collection '{self.__collection_name}'..."
            logger.debug(message)
            self.__vector_store_service.delete_documents(
                collection_name=self.__collection_name,
                document_ids=[uuid_id],
            )
        else:
            message = f"No embeddings found for '{uri}'"
            logger.debug(message)

        return {
            "status": "success",
            "message": message,
            "collection_name": self.__collection_name,
            "subject": parameters.s,
            "predicate": parameters.p,
            "object": parameters.o,
        }

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
