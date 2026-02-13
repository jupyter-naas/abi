from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict, List

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import BaseModel, Field

cache = CacheFactory.CacheFS_find_storage(subpath="triple_embeddings")


@dataclass
class CreateSearchToolWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateSearchTool workflow.

    vector_store: VectorStoreService
    embeddings_model: Embeddings
    """

    vector_store: VectorStoreService
    embeddings_model: Embeddings


class CreateSearchToolWorkflowParameters(WorkflowParameters):
    """Parameters for CreateSearchTool workflow execution.

    Attributes:
        collection_name: Name of the vector store collection
        search_param_name: Name of the search parameter (e.g., "person_name", "company_name")
        tool_name: Name of the search tool to create
        tool_description: Description of the search tool
        entity_type_label: Label for the entity type for logging
        filter: Metadata filter for the search. Available filters: uri, label, owl_type, type_uri, type_label
    """

    collection_name: Annotated[
        str, Field(..., description="Name of the vector store collection")
    ]
    search_param_name: Annotated[
        str,
        Field(
            ...,
            description="Name of the search parameter (e.g., 'person_name', 'company_name')",
        ),
    ]
    tool_name: Annotated[
        str, Field(..., description="Name of the search tool to create")
    ]
    tool_description: Annotated[
        str, Field(..., description="Description of the search tool")
    ]
    entity_type_label: Annotated[
        str, Field(..., description="Label for the entity type for logging")
    ]
    filter: Annotated[
        Dict[str, Any],
        Field(
            description="Metadata filter for the search. Available filters: uri, label, owl_type, type_uri, type_label",
        ),
    ]


class CreateSearchToolWorkflow(Workflow):
    """Workflow for creating a search tool for entities in a collection."""

    __configuration: CreateSearchToolWorkflowConfiguration

    def __init__(self, configuration: CreateSearchToolWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        # Get services from configuration
        self.__vector_store_service = self.__configuration.vector_store
        self.__embeddings_model = self.__configuration.embeddings_model

    @cache(
        lambda self, text: text,
        cache_type=DataType.PICKLE,
    )
    def create_vector_embedding(self, text: str) -> np.ndarray:
        """Create a vector embedding for a given text.

        Args:
            text: The text to create a vector embedding for

        Returns:
            The vector embedding
        """
        embedding = self.__embeddings_model.embed_query(text)
        embedding_array = np.array(embedding)
        return embedding_array

    def create_search_tool(
        self,
        parameters: CreateSearchToolWorkflowParameters,
    ) -> StructuredTool:
        """Create a search tool for entities in a collection.

        Args:
            parameters: Parameters for the search tool

        Returns:
            A StructuredTool for searching entities by name
        """

        # Create search schema dynamically
        class SearchSchema(BaseModel):
            __annotations__ = {
                parameters.search_param_name: str,
                "k": int,
            }
            # Annotate the search_param_name field
            locals()[parameters.search_param_name] = Field(
                description=f"The name of the {parameters.entity_type_label} to search for"
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
                name = kwargs.get(parameters.search_param_name, "")
                k = kwargs.get("k", 10)

                if not name:
                    return [{"error": f"{parameters.search_param_name} is required"}]

                # Generate embedding for the query
                query_embedding = self.__embeddings_model.embed_query(name)
                query_vector = np.array(query_embedding)

                # Search in vector store
                search_results = self.__vector_store_service.search_similar(
                    collection_name=parameters.collection_name,
                    query_vector=query_vector,
                    k=k,
                    filter=parameters.filter,
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
            name=parameters.tool_name,
            description=parameters.tool_description,
            func=search_entity,
            args_schema=SearchSchema,
        )

        return search_tool

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
