from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from marketplace.modules.ontology.integrations.AlgoliaIntegration import AlgoliaIntegration, AlgoliaIntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from typing import Dict, Any, List
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class SearchAlgoliaConfiguration(WorkflowConfiguration):
    """Configuration for SearchAlgolia workflow.
    
    Attributes:
        algolia_integration_config (AlgoliaIntegrationConfiguration): Configuration for Algolia integration
    """
    algolia_integration_config: AlgoliaIntegrationConfiguration

class SearchAlgoliaParameters(WorkflowParameters):
    """Parameters for SearchAlgolia execution.
    
    Attributes:
        index_name (str): Name of the Algolia index to search
        query (str): Search query string
        filters (str, optional): Filters to apply to the search
        page (int, optional): Page number for pagination
        hits_per_page (int, optional): Number of results per page
    """
    index_name: str = Field(default="abi-search", description="Name of the Algolia index to search")
    query: str = Field(..., description="Search query string")
    filters: str = Field(default="", description="Filters to apply to the search (e.g., 'type:assistant')")
    page: int = Field(default=0, description="Page number for pagination")
    hits_per_page: int = Field(default=20, description="Number of results per page")

class SearchAlgolia(Workflow):
    """Workflow for searching the Algolia index."""
    __configuration: SearchAlgoliaConfiguration
    
    def __init__(self, configuration: SearchAlgoliaConfiguration):
        self.__configuration = configuration
        self.__algolia = AlgoliaIntegration(self.__configuration.algolia_integration_config)

    def run(self, parameters: SearchAlgoliaParameters) -> Dict[str, Any]:
        """Searches the Algolia index with the given parameters.
        
        Args:
            parameters (SearchAlgoliaParameters): Search parameters
            
        Returns:
            Dict[str, Any]: Search results from Algolia
        """
        # Prepare search parameters
        search_params = {
            "page": parameters.page,
            "hitsPerPage": parameters.hits_per_page
        }
        
        # Add filters if provided
        if parameters.filters:
            search_params["filters"] = parameters.filters

        # Execute search
        results = self.__algolia.search(
            index_name=parameters.index_name,
            query=parameters.query,
            **search_params
        )
        
        return {
            "hits": results.get("hits", []),
            "nbHits": results.get("nbHits", 0),
            "page": results.get("page", 0),
            "nbPages": results.get("nbPages", 0),
            "hitsPerPage": results.get("hitsPerPage", parameters.hits_per_page),
            "processingTimeMS": results.get("processingTimeMS", 0)
        }

    def as_tools(self) -> List[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [StructuredTool(
            name="search_algolia",
            description="Search the Algolia index for content using keywords",
            func=self.run,
            args_schema=SearchAlgoliaParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/search_algolia")
        def search_algolia(parameters: SearchAlgoliaParameters):
            return self.run(parameters)

if __name__ == "__main__":
    from src import secret
    
    # Initialize Algolia configuration
    algolia_config = AlgoliaIntegrationConfiguration(
        app_id=secret.get("ALGOLIA_APPLICATION_ID"),
        api_key=secret.get("ALGOLIA_API_KEY")
    )
    
    # Create workflow configuration
    config = SearchAlgoliaConfiguration(
        algolia_integration_config=algolia_config
    )
    
    # Create and test workflow
    workflow = SearchAlgolia(config)
    result = workflow.run(SearchAlgoliaParameters(
        query="assistant",
        filters="type:assistant"
    ))
    print(result) 