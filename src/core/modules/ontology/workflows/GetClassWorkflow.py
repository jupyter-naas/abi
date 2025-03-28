from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import config
from dataclasses import dataclass
from pydantic import Field
from datetime import datetime, timedelta
from rdflib import Graph
from abi import logger
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class GetClassConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for GetClass workflow.
    
    Attributes:
        ontology_store (IOntologyStoreService): Ontology store service
    """
    ontology_store: IOntologyStoreService

class SearchClassWorkflowParameters(WorkflowParameters):
    """Parameters for SearchClass workflow.
    
    Attributes:
        search_label (str): Label to search for
    """
    search_label: str = Field(..., description="Class label to search for in the ontology schema.")

class SearchIndividualWorkflowParameters(WorkflowParameters):
    """Parameters for SearchIndividual workflow.
    
    Attributes:
        search_label (str): Label to search for
    """
    class_uri: str = Field(..., description="Class URI to use to search for individuals.")
    search_label: str = Field(..., description="Individual label to search for in the ontology schema.")

class GetAllIndividualsWorkflowParameters(WorkflowParameters):
    """Parameters for GetAllIndividuals workflow.
    
    Attributes:
        class_uri (str): Class URI
    """
    class_uri: str = Field(..., description="Class URI to use to get all individuals of this class.")

class GetClassWorkflow(Workflow):
    """Workflow for getting class instances from the ontology."""
    __configuration: GetClassConfigurationWorkflow
    
    def __init__(self, configuration: GetClassConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def results_to_list(self, results: list[dict]) -> list[dict]:
        data = []
        for row in results:
            data_dict = {}
            for key in row.labels:
                data_dict[key] = str(row[key]) if row[key] else None
            data.append(data_dict)
        return data
    
    def search_class(self, parameters: SearchClassWorkflowParameters) -> dict:
        graph = Graph()
        graph.parse("src/core/modules/ontology/ontologies/ConsolidatedOntology.ttl")

        """Find a class URI based on its label with fuzzy matching.
        
        Args:
            parameters: Search parameters containing the label to search for
            
        Returns:
            dict: Results containing matched class URIs and scores
        """
        query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT DISTINCT ?class ?label ?score ?definition ?example ?comment
        WHERE {
          # Find all classes in the ontology
          {
            ?class a owl:Class .
          } UNION {
            ?class a rdfs:Class .
          }
          
          # Create a score for each class based on matching properties
          {
            # Exact match with rdfs:label gets highest score (10)
            ?class rdfs:label ?label .
            FILTER(LCASE(STR(?label)) = LCASE(?searchLabel))
            BIND(10 AS ?score)
          } UNION {
            # Contains match with rdfs:label gets good score (8)
            ?class rdfs:label ?label .
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
            BIND(8 AS ?score)
          } UNION {
            # Exact match with skos:definition gets medium score (6)
            ?class skos:definition ?label .
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
            BIND(6 AS ?score)
          } UNION {
            # Contains match with skos:example gets lower score (4)
            ?class skos:example ?label .
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
            BIND(4 AS ?score)
          } UNION {
            # Contains match with skos:comment gets lowest score (2)
            ?class skos:comment ?label .
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
            BIND(2 AS ?score)
          }
          
          # Get additional properties if they exist
          OPTIONAL { ?class skos:definition ?definition }
          OPTIONAL { ?class skos:example ?example }
          OPTIONAL { ?class skos:comment ?comment }
        }
        ORDER BY DESC(?score)
        LIMIT 10
        """
        
        results = graph.query(
            query.replace("?searchLabel", f'"{parameters.search_label}"')
        )
        return self.results_to_list(results)
    
    def search_individual(self, parameters: SearchIndividualWorkflowParameters) -> dict:
        query = f"""
        SELECT DISTINCT ?class_uri ?individual_uri ?label (MAX(?temp_score) AS ?score)
        WHERE {{
            # Filter On Class URI and ensure individual is a NamedIndividual
            ?individual_uri a ?class_uri ;
                            a owl:NamedIndividual ;
                            rdfs:label ?label .
            FILTER(?class_uri = <{parameters.class_uri}>)
            
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
        results = self.__configuration.ontology_store.query(query)
        return self.results_to_list(results)

    def get_all_individuals(self, parameters: GetAllIndividualsWorkflowParameters) -> dict:
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?label
        WHERE {{
            ?class a <{parameters.class_uri}> ;
                    rdfs:label ?label .
        }}
        ORDER BY ?label
        """
        results = self.__configuration.ontology_store.query(query)
        return self.results_to_list(results)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="ontology_search_class",
                description="Find an ontology class URI based on its label. It will return the most relevant class URI using matching with rdfs:label, skos:definition, skos:example, skos:comment",
                func=lambda search_label: self.search_class(SearchClassWorkflowParameters(search_label=search_label)),
                args_schema=SearchClassWorkflowParameters
            ),
            StructuredTool(
                name="ontology_search_individual",
                description="Find an ontology individual based on its label. It will return the most relevant individual using matching with rdfs:label",
                func=lambda class_uri, search_label: self.search_individual(SearchIndividualWorkflowParameters(class_uri=class_uri, search_label=search_label)),
                args_schema=SearchIndividualWorkflowParameters
            ),
            StructuredTool(
                name="ontology_get_all_individuals",
                description="Get all individuals of a class from the ontology.",
                func=lambda class_uri: self.get_all_individuals(GetAllIndividualsWorkflowParameters(class_uri=class_uri)),
                args_schema=GetAllIndividualsWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass