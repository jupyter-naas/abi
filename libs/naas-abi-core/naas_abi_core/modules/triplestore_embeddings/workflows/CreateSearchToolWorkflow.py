from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
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
    """
    Parameters for configuring the CreateSearchTool workflow.

    Attributes:
        tool_name: Name to assign to the generated search tool.
        tool_description: Description of the created search tool and its purpose.
        search_param_name: The input parameter name that the search tool uses for querying. Defaults to "search_entity_name".
        search_param_description: Description for the querying parameter. Defaults to "Name of the entity to search for".
        collection_name: Name of the vector store collection to be searched. Optional.
        search_filter: A dictionary for metadata filtering during search (available keys: uri, label, owl_type, type_uri, type_label). Optional.
        k: The number of search results to return (default: 10; min: 1, max: 20).
        threshold: Minimum similarity score threshold for result filtering (float between 0.0 and 1.0, default: 0.80).
    """

    tool_name: Annotated[
        str, Field(..., description="Name of the search tool to create")
    ]
    tool_description: Annotated[
        str, Field(..., description="Description of the search tool")
    ]
    search_param_name: Annotated[
        str,
        Field(
            ...,
            description="Name of the parameter for the search tool",
        ),
    ] = "search_entity_name"
    search_param_description: Annotated[
        str,
        Field(
            ...,
            description="Description of the parameter for the search tool",
        ),
    ] = "Name of the entity to search for"
    collection_name: Optional[
        Annotated[
            str,
            Field(description="Name of the vector store collection"),
        ]
    ] = ""
    search_filter: Optional[
        Annotated[
            Dict[str, Any],
            Field(
                description="Filter for the search. Available filters: uri, label, owl_type, type_uri, type_label",
            ),
        ]
    ] = {}
    k: Optional[
        Annotated[
            int,
            Field(
                ge=1,
                le=20,
                description="Number of results to return",
            ),
        ]
    ] = 10
    threshold: Optional[
        Annotated[
            float,
            Field(
                ge=0.0,
                le=1.0,
                description="Threshold for filtering results",
            ),
        ]
    ] = 0.5


class CreateSearchToolWorkflow(Workflow):
    """Workflow for creating a search tool for entities in a collection."""

    __configuration: CreateSearchToolWorkflowConfiguration
    __embeddings_utils: EmbeddingsUtils

    def __init__(self, configuration: CreateSearchToolWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        # Get services from configuration
        self.__vector_store_service = self.__configuration.vector_store
        self.__embeddings_model = self.__configuration.embeddings_model
        self.__embeddings_utils = EmbeddingsUtils(
            embeddings_model=self.__embeddings_model
        )

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
                "collection_name": str,
                "search_filter": Dict[str, Any],
                "k": int,
                "threshold": float,
            }
            # Annotate the search_param_name field
            locals()[parameters.search_param_name] = Annotated[
                str, Field(description=parameters.search_param_description)
            ]

            # Annotate static fields
            collection_name: Optional[
                Annotated[
                    str,
                    Field(
                        description="Name of the vector store collection",
                    ),
                ]
            ] = parameters.collection_name
            search_filter: Optional[
                Annotated[
                    Dict[str, Any],
                    Field(
                        description="Filter for the search. Available filters: uri, label, owl_type, type_uri, type_label",
                    ),
                ]
            ] = parameters.search_filter
            k: Optional[
                Annotated[
                    int,
                    Field(
                        ge=1,
                        le=20,
                        description="Number of results to return",
                    ),
                ]
            ] = parameters.k
            threshold: Optional[
                Annotated[
                    float,
                    Field(
                        ge=0.0,
                        le=1.0,
                        description="Threshold for filtering results",
                    ),
                ]
            ] = parameters.threshold

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
                collection_name = kwargs.get(
                    "collection_name", parameters.collection_name
                )
                search_filter = kwargs.get("search_filter", parameters.search_filter)
                k = kwargs.get("k", parameters.k)
                threshold = kwargs.get("threshold", parameters.threshold)

                if not name:
                    return [{"error": f"{parameters.search_param_name} is required"}]

                if not collection_name:
                    return [{"error": "Collection name is required"}]

                # Generate embedding for the query
                query_vector = self.__embeddings_utils.create_vector_embedding(name)

                # Search in vector store
                search_results = self.__vector_store_service.search_similar(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    k=k,
                    filter=search_filter,
                    include_metadata=True,
                )

                # Format results
                results = []
                for result in search_results:
                    if (
                        result.metadata
                        and result.score is not None
                        and isinstance(result.score, float)
                        and result.score >= threshold
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
            func=lambda **kwargs: search_entity(**kwargs),
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
