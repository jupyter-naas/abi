from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from rdflib import Graph
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import glob
import os
from abi.utils.SPARQL import results_to_list

@dataclass
class SearchClassConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for SearchClass workflow."""
    triple_store: ITripleStoreService

class SearchClassWorkflowParameters(WorkflowParameters):
    """Parameters for SearchClass workflow."""
    search_label: str = Field(..., description="Class label to search for in the ontology schema.")

class SearchClassWorkflow(Workflow):
    """Workflow for searching ontology classes."""
    __configuration: SearchClassConfigurationWorkflow
    
    def __init__(self, configuration: SearchClassConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def merge_ontologies(self) -> Graph:
        """Merge all ontologies from src/core/** and src/custom/** into a single graph.
        
        Returns:
            Graph: The merged graph containing all ontologies
        """
        # Initialize merged graph
        merged_graph = Graph()
        
        # Get all .ttl files from src/core and src/custom
        ontology_files = []
        for path in ['src/core', 'src/custom']:
            ontology_files.extend(glob.glob(os.path.join(path, '**/*.ttl'), recursive=True))
            
        # Merge each ontology file into consolidated graph
        for ontology_file in ontology_files:
            try:
                # Parse and merge each ontology file
                merged_graph.parse(ontology_file, format='turtle')
            except Exception as e:
                continue
                
        return merged_graph

    def search_class(self, parameters: SearchClassWorkflowParameters) -> dict:
        """Find a class URI based on its label with fuzzy matching.
        
        Args:
            parameters: Search parameters containing the label to search for
            
        Returns:
            dict: Results containing matched class URIs and scores
        """
        graph = self.merge_ontologies()
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
        return results_to_list(results)
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_search_class",
                description="Search an ontology class URI based on its label. It will return the most relevant class URI using matching with rdfs:label, skos:definition, skos:example, skos:comment",
                func=lambda search_label: self.search_class(SearchClassWorkflowParameters(search_label=search_label)),
                args_schema=SearchClassWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 