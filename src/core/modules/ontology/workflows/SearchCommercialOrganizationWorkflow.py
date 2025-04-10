from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from abi.utils.SPARQL import results_to_list

@dataclass
class SearchCommercialOrganizationConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for SearchCommercialOrganization workflow."""
    triple_store: ITripleStoreService

class SearchCommercialOrganizationWorkflowParameters(WorkflowParameters):
    """Parameters for SearchCommercialOrganization workflow."""
    search_label: str = Field(..., description="Name of the commercial organization to search for in the ontology schema.")

class SearchCommercialOrganizationWorkflow(Workflow):
    """Workflow for searching commercial organizations in the ontology."""
    __configuration: SearchCommercialOrganizationConfigurationWorkflow
    
    def __init__(self, configuration: SearchCommercialOrganizationConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_commercial_organization(self, parameters: SearchCommercialOrganizationWorkflowParameters) -> dict:
        class_uri = "https://www.commoncoreontologies.org/ont00000443"  # URI for Commercial Organization
        query = f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
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
                name="ontology_search_commercial_organization",
                description="Search an ontology commercial organization based on its name.",
                func=lambda search_label: self.search_commercial_organization(
                    SearchCommercialOrganizationWorkflowParameters(search_label=search_label)
                ),
                args_schema=SearchCommercialOrganizationWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 