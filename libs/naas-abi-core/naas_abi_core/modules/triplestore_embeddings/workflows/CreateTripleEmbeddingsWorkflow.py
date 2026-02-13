from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict, List

from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from naas_abi_core import logger
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field
from rdflib import OWL, RDFS, Literal, URIRef
from rdflib.query import ResultRow


@dataclass
class CreateTripleEmbeddingsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateTripleEmbeddings workflow.

    triple_store: ITripleStoreService
    vector_store: VectorStoreService
    embeddings_model: Embeddings
    collection_name: str = "triple_embeddings"
    """

    vector_store: VectorStoreService
    triple_store: ITripleStoreService
    embeddings_model: Embeddings
    embeddings_dimension: int
    collection_name: str = "triple_embeddings"


class CreateTripleEmbeddingsWorkflowParameters(WorkflowParameters):
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


class CreateTripleEmbeddingsWorkflow(Workflow):
    """Workflow for creating embeddings for named individuals of a given class and storing them in a vector store."""

    __configuration: CreateTripleEmbeddingsWorkflowConfiguration
    __embeddings_utils: EmbeddingsUtils

    def __init__(self, configuration: CreateTripleEmbeddingsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        # Get services from configuration
        self.__triple_store_service = self.__configuration.triple_store
        self.__vector_store_service = self.__configuration.vector_store
        self.__embeddings_model = self.__configuration.embeddings_model
        self.__embeddings_dimension = self.__configuration.embeddings_dimension
        self.__collection_name = self.__configuration.collection_name

        # Init embeddings utils
        self.__embeddings_utils = EmbeddingsUtils(
            embeddings_model=self.__embeddings_model
        )

    def get_rdf_type_from_subject(self, subject: URIRef | str) -> List[Dict[str, Any]]:
        """Get the RDF type from a given subject.

        Args:
            subject: The subject of the triple

        Returns:
            The RDF type of the subject
        """
        sparql_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?type ?label
            WHERE {{
                <{str(subject)}> rdf:type ?type .
                ?type rdfs:label ?label .
            }}
        """
        rdf_types: List[Dict] = []
        results = self.__triple_store_service.query(sparql_query)
        for row in results:
            assert isinstance(row, ResultRow)
            rdf_types.append({"type": row.type, "label": row.label})
        return rdf_types

    def create_triple_embeddings(
        self, parameters: CreateTripleEmbeddingsWorkflowParameters
    ) -> Dict[str, Any]:
        """Create embeddings for a given triple and store them in a vector store.

        Args:
            parameters: The workflow parameters containing s, p, and o.

        Returns:
            A dictionary containing the number of entities processed and collection information
        """
        logger.info(
            f"Creating embeddings triple '{parameters.s} {parameters.p} {parameters.o}' in collection '{self.__collection_name}'..."
        )
        # Init
        uri = str(parameters.s)
        uuid_id = EmbeddingsUtils.create_uuid_from_string(uri)
        label = str(parameters.o)
        metadata: Dict[str, Any] = {"uri": uri, "label": label}

        # Add metadata: Get RDF types from subject
        rdf_types = self.get_rdf_type_from_subject(parameters.s)
        if len(rdf_types) == 0:
            logger.error(f"No RDF types found for {parameters.s}")
            return {
                "status": "error",
                "message": f"No RDF types found for {parameters.s}",
            }

        owl_types: List[str] = []
        type_uris: List[str] = []
        type_labels: List[str] = []
        for rdf_type in rdf_types:
            # If the type is from OWL namespace, add its URI to "owl"
            if str(rdf_type["type"]).startswith(str(OWL)):
                # Collect all OWL types
                owl_types.append(str(rdf_type["type"]))
            else:
                # Otherwise accumulate its type and label
                type_uris.append(str(rdf_type["type"]))
                type_labels.append(str(rdf_type["label"]))

        # If any non-OWL types were found, add them as lists
        if type_uris and type_labels:
            metadata["type_uri"] = type_uris
            metadata["type_label"] = type_labels
        if owl_types:
            metadata["owl_type"] = owl_types

        # Ensure collection exists
        self.__vector_store_service.ensure_collection(
            collection_name=self.__collection_name,
            dimension=self.__embeddings_dimension,
            distance_metric="cosine",
        )

        # Check if embeddings already exist for this UUID
        existing_doc = self.__vector_store_service.get_document(
            collection_name=self.__collection_name,
            document_id=uuid_id,
            include_vector=False,
        )
        if existing_doc is None:
            logger.info(
                f"Creating embeddings for '{label}' in collection '{self.__collection_name}'..."
            )
            embedding_array = self.__embeddings_utils.create_vector_embedding(label)

            # Store in vector store
            logger.info("Storing embeddings in collection...")
            self.__vector_store_service.add_documents(
                collection_name=self.__collection_name,
                ids=[uuid_id],
                vectors=[embedding_array],
                metadata=[metadata],
            )
        elif (
            not (isinstance(existing_doc.metadata, dict) and isinstance(metadata, dict))
            or any((existing_doc.metadata.get(k) != v) for k, v in metadata.items())
            or any((metadata.get(k) != v) for k, v in existing_doc.metadata.items())
        ):
            logger.warning(f"Updating embeddings for '{label}': metadata has changed")
            self.__vector_store_service.update_document(
                collection_name=self.__collection_name,
                document_id=uuid_id,
                metadata=metadata,
            )
        else:
            logger.info(f"Embeddings already exist for '{label}'")

        return {
            "status": "success",
            "collection_name": self.__collection_name,
            "subject": parameters.s,
            "predicate": parameters.p,
            "object": parameters.o,
            "metadata": metadata,
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
