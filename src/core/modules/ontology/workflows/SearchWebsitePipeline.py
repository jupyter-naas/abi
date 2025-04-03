from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi.utils.SPARQL import results_to_list

@dataclass
class SearchWebsiteConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for SearchWebsite workflow."""
    triple_store: ITripleStoreService

class SearchWebsiteWorkflowParameters(WorkflowParameters):
    """Parameters for SearchWebsite workflow."""
    search_label: str = Field(..., description="Website URL to search for")
    
class SearchWebsiteWorkflow(Workflow):
    """Workflow for searching websites in the ontology."""
    __configuration: SearchWebsiteConfigurationWorkflow
    
    def __init__(self, configuration: SearchWebsiteConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_website(self, parameters: SearchWebsiteWorkflowParameters) -> dict:
        class_uri = "http://ontology.naas.ai/abi/Website"
        query = f"""
        SELECT DISTINCT ?class_uri ?individual_uri ?label (MAX(?temp_score) AS ?score)
        WHERE {{
            # Filter On Class URI and ensure individual is a NamedIndividual
            ?individual_uri a ?class_uri ;
                            a owl:NamedIndividual ;
                            rdfs:label ?label .
            FILTER(?class_uri = <{class_uri}>)
            
            # Calculate scores for perfect and partial matches
            BIND(IF(LCASE(STR(?label)) = LCASE("{parameters.search_label}"), 10, 0) AS ?perfect_score)
            BIND(IF(CONTAINS(LCASE(STR(?label)), LCASE("{parameters.search_label}")), 8, 0) AS ?partial_score)
            
            # Use the higher of the two scores
            BIND(IF(?perfect_score > ?partial_score, ?perfect_score, ?partial_score) AS ?temp_score)
            
            # Only include results with a score > 0
            FILTER(?temp_score > 0)
        }}
        GROUP BY ?class_uri ?individual_uri ?label
        ORDER BY DESC(?score) ?label
        """
        results = self.__configuration.triple_store.query(query)
        return results_to_list(results)

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_search_website",
                description="Search for websites in the ontology",
                func=lambda **kwargs: self.search_website(SearchWebsiteWorkflowParameters(**kwargs)),
                args_schema=SearchWebsiteWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 