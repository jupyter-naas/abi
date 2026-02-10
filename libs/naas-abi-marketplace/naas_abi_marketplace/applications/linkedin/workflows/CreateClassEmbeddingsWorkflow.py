from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict, List

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.agent.beta.Embeddings import (
    embeddings,
    embeddings_batch,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import BaseModel, Field


@dataclass
class CreateClassEmbeddingsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateClassEmbeddings workflow.

    This workflow doesn't require any configuration.
    """

    triple_store: ITripleStoreService
    vector_store: VectorStoreService
    embeddings_model_name: str = "text-embedding-ada-002"
    embeddings_dimension: int = 1536


class CreateClassEmbeddingsWorkflowParameters(WorkflowParameters):
    """Parameters for CreateClassEmbeddings workflow execution.

    Attributes:
        class_uri (str): The URI of the class to query (e.g., "cco:ont00001262")
        collection_name (str): Name of the vector store collection
        entity_variable_name (str): Variable name for the entity in SPARQL query (e.g., "person", "company")
        entity_type_label (str): Label for the entity type for logging (e.g., "person", "company")
    """

    class_uri: Annotated[
        str,
        Field(
            ..., description="The URI of the class to query (e.g., 'cco:ont00001262')"
        ),
    ]
    collection_name: Annotated[
        str, Field(..., description="Name of the vector store collection")
    ]
    entity_variable_name: Annotated[
        str,
        Field(
            ...,
            description="Variable name for the entity in SPARQL query (e.g., 'person', 'company')",
        ),
    ]
    entity_type_label: Annotated[
        str,
        Field(
            ...,
            description="Label for the entity type for logging (e.g., 'person', 'company')",
        ),
    ]


class CreateClassEmbeddingsWorkflow(Workflow):
    """Workflow for creating embeddings for entities of a given class and storing them in a vector store."""

    __configuration: CreateClassEmbeddingsWorkflowConfiguration

    def __init__(self, configuration: CreateClassEmbeddingsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        # Get services from configuration
        self.__triple_store_service = self.__configuration.triple_store
        self.__vector_store_service = self.__configuration.vector_store

        # Get embedding dimension and model name
        self.__embedding_dimension = self.__configuration.embeddings_dimension
        self.__embeddings_model_name = self.__configuration.embeddings_model_name

    def create_class_embeddings(
        self, parameters: CreateClassEmbeddingsWorkflowParameters
    ) -> Dict[str, Any]:
        """Create embeddings for entities of a given class and store them in a vector store.

        Args:
            parameters: The workflow parameters containing class_uri, collection_name, etc.

        Returns:
            A dictionary containing the number of entities processed and collection information
        """
        logger.debug(
            f"==> Creating embeddings for class {parameters.class_uri} in collection {parameters.collection_name}"
        )

        # Ensure collection exists
        self.__vector_store_service.ensure_collection(
            collection_name=parameters.collection_name,
            dimension=self.__embedding_dimension,
            distance_metric="cosine",
        )

        # Query entities from triple store with all datatype properties
        sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX cco: <https://www.commoncoreontologies.org/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>

            SELECT DISTINCT ?{parameters.entity_variable_name} ?label ?property ?value
            WHERE {{
                ?{parameters.entity_variable_name} a {parameters.class_uri} ;
                        rdfs:label ?label .
                OPTIONAL {{
                    ?{parameters.entity_variable_name} ?property ?value .
                    ?property a owl:DatatypeProperty .
                }}
            }}
        """
        results = self.__triple_store_service.query(sparql_query)
        sparql_utils = SPARQLUtils(self.__triple_store_service)
        results_list: List[Dict[str, Any]] = sparql_utils.results_to_list(results) or []
        if len(results_list) == 0:
            logger.warning(f"No entities found for class {parameters.class_uri}")
            return {
                "status": "success",
                "entities_processed": 0,
            }

        # Prepare data for embedding
        # Group by entity to collect all datatype properties
        entity_data: Dict[str, Dict[str, Any]] = {}

        for row in results_list:
            entity_uri = str(row.get(parameters.entity_variable_name, ""))
            entity_label = str(row.get("label", ""))
            property_uri = row.get("property")
            property_value = row.get("value")

            if entity_uri and entity_label:
                if entity_uri not in entity_data:
                    entity_data[entity_uri] = {
                        "uri": str(entity_uri),
                        "label": str(entity_label),
                        "properties": {},
                    }

                # Add datatype property if it exists
                if property_uri and property_value is not None:
                    property_uri_str = str(property_uri)
                    # Convert property value to string, handling different types
                    if isinstance(property_value, str):
                        value_str = property_value
                    else:
                        value_str = str(property_value)
                    entity_data[entity_uri]["properties"][property_uri_str] = value_str

        # Convert to lists for processing
        labels: List[str] = []
        uris: List[str] = []
        metadata: List[Dict[str, Any]] = []

        for entity_uri, data in entity_data.items():
            labels.append(data["label"])
            uris.append(entity_uri)
            # Include all datatype properties in metadata
            metadata.append(
                {
                    "uri": data["uri"],
                    "label": data["label"],
                    **data["properties"],  # Add all datatype properties as metadata
                }
            )

        # Check which embeddings already exist
        doc_ids = [uri.split("/")[-1] for uri in uris]
        existing_doc_ids = set()

        if doc_ids:
            logger.debug(
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
                new_labels.append(labels[i])
                new_uris.append(uris[i])
                new_metadata.append(metadata[i])
                new_doc_ids.append(doc_id)

        # Embed labels and store in vector store for new entities only
        if new_labels:
            logger.info(
                f"Embedding {len(new_labels)} new {parameters.entity_type_label} labels..."
            )
            embeddings_vectors = embeddings_batch(new_labels)
            embeddings_array = [np.array(emb) for emb in embeddings_vectors]

            # Store in vector store
            self.__vector_store_service.add_documents(
                collection_name=parameters.collection_name,
                ids=new_doc_ids,
                vectors=embeddings_array,
                metadata=new_metadata,
            )
            logger.info(
                f"Stored {len(new_labels)} new {parameters.entity_type_label} embeddings in vector store"
            )

            return {
                "status": "success",
                "entities_processed": len(new_labels),
                "collection_name": parameters.collection_name,
                "entity_type": parameters.entity_type_label,
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
                default=5,
                ge=1,
                le=20,
                description="Number of results to return (default: 5)",
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
                k = kwargs.get("k", 5)

                if not name:
                    return [{"error": f"{search_param_name} is required"}]

                # Generate embedding for the query
                query_embedding = embeddings(name)
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
                    if result.metadata:
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
                name="create_class_embeddings",
                description="Create embeddings for entities of a given class and store them in a vector store.",
                func=lambda **kwargs: self.create_class_embeddings(
                    CreateClassEmbeddingsWorkflowParameters(**kwargs)
                ),
                args_schema=CreateClassEmbeddingsWorkflowParameters,
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
    from naas_abi_marketplace.applications.linkedin import ABIModule

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.linkedin"])

    module: ABIModule = ABIModule.get_instance()

    configuration = CreateClassEmbeddingsWorkflowConfiguration(
        triple_store=module.engine.services.triple_store,
        vector_store=module.engine.services.vector_store,
    )
    workflow = CreateClassEmbeddingsWorkflow(configuration)
    result = workflow.create_class_embeddings(
        CreateClassEmbeddingsWorkflowParameters(
            class_uri="cco:ont00001262",
            collection_name="linkedin_persons",
            entity_variable_name="person",
            entity_type_label="person",
        )
    )
    print(result)
