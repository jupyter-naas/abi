from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi.utils.SPARQL import results_to_list
from abi import logger

@dataclass
class SearchLinkedInPageConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for SearchLinkedInPage workflow."""
    triple_store: ITripleStoreService

class SearchLinkedInPageWorkflowParameters(WorkflowParameters):
    """Parameters for SearchLinkedInPage workflow."""
    search_label: str = Field(..., description="LinkedIn page URL to search for")

class SearchLinkedInPageWorkflow(Workflow):
    """Workflow for searching LinkedIn pages in the ontology."""
    __configuration: SearchLinkedInPageConfigurationWorkflow
    
    def __init__(self, configuration: SearchLinkedInPageConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_linkedin(self, parameters: SearchLinkedInPageWorkflowParameters) -> dict:
        class_uri = "http://ontology.naas.ai/abi/LinkedInPage"
        # Get all subclasses of LinkedInPage
        subclasses_query = """
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT DISTINCT ?subclass
            WHERE {
                ?subclass rdfs:subClassOf+ abi:LinkedInPage .
            }
        """
        subclasses = self.__configuration.triple_store.query(subclasses_query)
        
        # Create VALUES clause instead of UNION
        subclasses_values = "VALUES ?subclass {" + " ".join([f"<{str(row['subclass'])}>" for row in subclasses]) + "}"
        logger.info(f"Subclasses: {subclasses_values}")

        # Main query using dynamic LinkedInPage types
        query = f"""
        SELECT DISTINCT ?class_uri ?individual_uri ?label (MAX(?temp_score) AS ?score)
        WHERE {{
            # Filter On Class URI and ensure individual is a NamedIndividual
            ?individual_uri a ?class_uri ;
                            a owl:NamedIndividual ;
                            rdfs:label ?label .
            FILTER(?class_uri IN ({subclasses_values}))
            
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
                name="ontology_search_linkedin_page",
                description="Search for LinkedIn pages in the ontology",
                func=lambda **kwargs: self.search_linkedin(SearchLinkedInPageWorkflowParameters(**kwargs)),
                args_schema=SearchLinkedInPageWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 