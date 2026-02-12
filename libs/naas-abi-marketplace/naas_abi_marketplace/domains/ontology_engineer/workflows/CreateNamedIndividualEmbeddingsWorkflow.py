from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict, List

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import OpenAIEmbeddings
from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import BaseModel, Field


@dataclass
class CreateNamedIndividualEmbeddingsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateNamedIndividualEmbeddings workflow.

    triple_store: ITripleStoreService
    vector_store: VectorStoreService
    embeddings_model_name: str = "text-embedding-3-large"
    embeddings_dimension: int = 3072
    """

    vector_store: VectorStoreService
    embeddings_model_name: str = "text-embedding-3-large"
    embeddings_dimension: int = 3072


class CreateNamedIndividualEmbeddingsWorkflowParameters(WorkflowParameters):
    """Parameters for CreateNamedIndividualEmbeddings workflow execution.

    Attributes:
        class_uri (str): The URI of the class to get individuals from
        collection_name (str): Name of the vector store collection
    """

    collection_name: Annotated[
        str, Field(..., description="Name of the vector store collection")
    ]
    uris: Annotated[
        List[str], Field(..., description="List of URIs to create embeddings for")
    ] = []
    labels: Annotated[
        List[str], Field(..., description="List of labels to get individuals from")
    ] = []
    metadata: Annotated[
        List[Dict[str, Any]],
        Field(..., description="List of metadata to get individuals from"),
    ] = []


class CreateNamedIndividualEmbeddingsWorkflow(Workflow):
    """Workflow for creating embeddings for named individuals of a given class and storing them in a vector store."""

    __configuration: CreateNamedIndividualEmbeddingsWorkflowConfiguration

    def __init__(
        self, configuration: CreateNamedIndividualEmbeddingsWorkflowConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration

        # Get services from configuration
        self.__vector_store_service = self.__configuration.vector_store
        self.__embedding_dimension = self.__configuration.embeddings_dimension
        self.__embeddings_model_name = self.__configuration.embeddings_model_name

    def get_individuals_from_class(
        self,
        class_uri: str,
        triple_store_service: ITripleStoreService,
    ) -> tuple[List[str], List[str], List[Dict[str, Any]]]:
        """Get individuals from a given class.

        Args:
            class_uri: The URI of the class to get individuals from

        Returns:
            A tuple containing lists of labels, URIs, and metadata
        """
        # Query entities from triple store (only URI and label)
        sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX cco: <https://www.commoncoreontologies.org/>

            SELECT DISTINCT ?uri ?label
            WHERE {{
                ?uri a <{class_uri}> ;
                        rdfs:label ?label .
            }}
        """
        results = triple_store_service.query(sparql_query)
        sparql_utils = SPARQLUtils(triple_store_service)
        results_list: List[Dict[str, Any]] = sparql_utils.results_to_list(results) or []
        if len(results_list) == 0:
            logger.warning(f"No entities found for class {class_uri}")
            return [], [], []

        # Prepare data for embedding (only URI and label)
        labels: List[str] = []
        uris: List[str] = []
        metadata: List[Dict[str, Any]] = []

        # Use a set to track unique entities
        seen_entities = set()

        for row in results_list:
            entity_uri = str(row.get("uri", ""))
            entity_label = str(row.get("label", ""))

            if entity_uri and entity_label and entity_uri not in seen_entities:
                seen_entities.add(entity_uri)
                labels.append(entity_label)
                uris.append(entity_uri)
                # Only include URI in metadata
                metadata.append({"uri": entity_uri, "label": entity_label})
        return labels, uris, metadata

    def create_named_individual_embeddings(
        self, parameters: CreateNamedIndividualEmbeddingsWorkflowParameters
    ) -> Dict[str, Any]:
        """Create embeddings for named individuals of a given class and store them in a vector store.

        Args:
            parameters: The workflow parameters containing class_uri and collection_name.

        Returns:
            A dictionary containing the number of entities processed and collection information
        """
        print(f"==> Creating embeddings in collection {parameters.collection_name}")

        # Ensure collection exists
        self.__vector_store_service.ensure_collection(
            collection_name=parameters.collection_name,
            dimension=self.__embedding_dimension,
            distance_metric="cosine",
        )

        # Check which embeddings already exist
        doc_ids = [uri.split("/")[-1] for uri in parameters.uris]
        existing_doc_ids = set()

        if doc_ids:
            print(
                f"Checking for existing embeddings in collection {parameters.collection_name}..."
            )
            for doc_id in doc_ids:
                existing_doc = self.__vector_store_service.get_document(
                    collection_name=parameters.collection_name,
                    document_id=doc_id,
                    include_vector=False,
                )
                if existing_doc is not None:
                    existing_doc_ids.add(doc_id)

        # Filter out entities that already have embeddings
        new_labels: List[str] = []
        new_uris: List[str] = []
        new_metadata: List[Dict[str, Any]] = []
        new_doc_ids: List[str] = []

        for i, doc_id in enumerate(doc_ids):
            if doc_id not in existing_doc_ids:
                new_labels.append(parameters.labels[i])
                new_uris.append(parameters.uris[i])
                new_metadata.append(parameters.metadata[i])
                new_doc_ids.append(doc_id)

        # Embed labels and store in vector store for new entities only
        if new_labels:
            print(
                f"Creating {len(new_labels)} embeddings for collection {parameters.collection_name}..."
            )

            embeddings_model = OpenAIEmbeddings(
                model=self.__embeddings_model_name,
                dimensions=self.__embedding_dimension,
            )
            embeddings_vectors = embeddings_model.embed_documents(
                new_labels, chunk_size=1000
            )
            embeddings_array = [np.array(vector) for vector in embeddings_vectors]

            # Store in vector store
            print(
                f"Storing {len(new_doc_ids)} new embeddings in collection {parameters.collection_name}"
            )
            self.__vector_store_service.add_documents(
                collection_name=parameters.collection_name,
                ids=new_doc_ids,
                vectors=embeddings_array,
                metadata=new_metadata,
            )

            return {
                "status": "success",
                "entities_processed": len(new_labels),
                "collection_name": parameters.collection_name,
            }
        else:
            logger.info("No new entities to embed")
            return {"status": "success", "entities_processed": 0}

    def create_search_tool(
        self,
        collection_name: str,
        search_param_name: str,
        tool_name: str,
        tool_description: str,
        entity_type_label: str,
    ) -> StructuredTool:
        """Create a search tool for entities in a collection.

        Args:
            collection_name: Name of the vector store collection
            search_param_name: Name of the search parameter (e.g., "person_name", "company_name")
            tool_name: Name of the search tool to create
            tool_description: Description of the search tool
            entity_type_label: Label for the entity type for logging

        Returns:
            A StructuredTool for searching entities by name
        """

        # Create search schema dynamically
        class SearchSchema(BaseModel):
            __annotations__ = {
                search_param_name: str,
                "k": int,
            }
            # Annotate the search_param_name field
            locals()[search_param_name] = Field(
                description=f"The name of the {entity_type_label} to search for"
            )
            # Annotate the "k" field with bounds and default.
            k: int = Field(
                default=10,
                ge=1,
                le=20,
                description="Number of results to return (default: 5)",
            )
            threshold: float = Field(
                default=0.80,
                ge=0.0,
                le=1.0,
                description="Threshold for filtering results (default: 0.95)",
            )

        # Create search function that accepts the dynamic parameter name
        def search_entity(**kwargs) -> List[Dict[str, Any]]:
            """Search for entity URIs by name using vector similarity search.

            Args:
                **kwargs: Must contain the search_param_name and optionally 'k'

            Returns:
                List of dictionaries containing entity URI, label, and similarity score
            """
            try:
                # Extract the name parameter using the search_param_name
                name = kwargs.get(search_param_name, "")
                k = kwargs.get("k", 10)
                embeddings_model = OpenAIEmbeddings(
                    model=self.__embeddings_model_name,
                    dimensions=self.__embedding_dimension,
                )

                if not name:
                    return [{"error": f"{search_param_name} is required"}]

                # Generate embedding for the query
                query_embedding = embeddings_model.embed_query(name)
                query_vector = np.array(query_embedding)

                # Search in vector store
                search_results = self.__vector_store_service.search_similar(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    k=k,
                    include_metadata=True,
                )

                # Format results
                results = []
                for result in search_results:
                    if (
                        result.metadata
                        and result.score is not None
                        and isinstance(result.score, float)
                        and result.score >= kwargs.get("threshold", 0.8)
                    ):
                        results.append(
                            {
                                "uri": result.metadata.get("uri", ""),
                                "label": result.metadata.get("label", ""),
                                "score": float(result.score),
                            }
                        )

                return results
            except Exception as e:
                return [{"error": str(e)}]

        # Create and return the search tool
        search_tool = StructuredTool(
            name=tool_name,
            description=tool_description,
            func=search_entity,
            args_schema=SearchSchema,
        )

        return search_tool

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="create_named_individual_embeddings",
                description="Create embeddings for named individuals of a given class and store them in a vector store.",
                func=lambda **kwargs: self.create_named_individual_embeddings(
                    CreateNamedIndividualEmbeddingsWorkflowParameters(**kwargs)
                ),
                args_schema=CreateNamedIndividualEmbeddingsWorkflowParameters,
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
        pass


if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.domains.ontology_engineer import ABIModule

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.domains.ontology_engineer"])

    module: ABIModule = ABIModule.get_instance()

    configuration = CreateNamedIndividualEmbeddingsWorkflowConfiguration(
        vector_store=module.engine.services.vector_store,
    )
    workflow = CreateNamedIndividualEmbeddingsWorkflow(configuration)

    labels, uris, metadata = workflow.get_individuals_from_class(
        class_uri="https://www.commoncoreontologies.org/ont00001180",
        triple_store_service=module.engine.services.triple_store,
    )
    result = workflow.create_named_individual_embeddings(
        CreateNamedIndividualEmbeddingsWorkflowParameters(
            collection_name="Organization",
            labels=labels,
            uris=uris,
            metadata=metadata,
        )
    )
    print(result)
