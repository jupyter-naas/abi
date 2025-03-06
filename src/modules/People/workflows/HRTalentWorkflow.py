from lib.abi.workflow import Workflow, WorkflowConfiguration
from lib.abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class HRTalentWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for HRTalentWorkflow.
    
    Attributes:
        None for now - can be extended based on needs
    """
    pass

class TalentFinderParameters(BaseModel):
    """Parameters for talent finding operations.
    
    Attributes:
        skill_name (str): Name of the skill to search for
        min_experience_years (int, optional): Minimum years of experience required
        position (str, optional): Specific position to filter by
    """
    skill_name: str = Field(..., description="Name of the skill to search for")

class SchemaParameters(BaseModel):
    """Parameters for getting the ontology schema.
    Currently empty as we don't need parameters, but can be extended if needed.
    """
    pass

class QueryParameters(BaseModel):
    """Parameters for executing a SPARQL query.
    
    Attributes:
        query (str): The SPARQL query to execute
        format (str, optional): The format to return results in. Defaults to "turtle" for CONSTRUCT/DESCRIBE queries
    """
    query: str = Field(..., description="The SPARQL query to execute")
    format: str = Field("turtle", description="Format for results (turtle, json, etc). Only applies to CONSTRUCT/DESCRIBE queries")

class HRTalentWorkflow(Workflow):
    """Workflow for managing HR talent-related operations.
    
    This workflow handles various HR talent management tasks including:
    - Talent finding
    - Schema retrieval
    """
    
    __configuration: HRTalentWorkflowConfiguration
    
    def __init__(self, configuration: HRTalentWorkflowConfiguration):
        self.__configuration = configuration
    
    def talent_finder(self, parameters: TalentFinderParameters) -> Dict[str, Any]:
        """Finds talent based on the given parameters.
        
        Args:
            parameters: Talent finder parameters
            
        Returns:
            Dict containing the talent search results
        """

        # Hardcoded for now.
        from lib.abi.utils.Graph import ABIGraph as Graph
        from lib.abi.services.ontology_store.OntologyFactory import OntologyStoreFactory
        from lib.abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
        
        triplestore : IOntologyStoreService = OntologyStoreFactory.OntologyStoreServiceFilesystem("storage/triplestore/People")
        
        results : Graph = triplestore.query("""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?person
        WHERE {
            ?skill a abi:ProfessionalSkills ;
                  rdfs:label ?label ;
                  abi:isSkillOf ?person .
            FILTER(CONTAINS(LCASE(?label), LCASE(""" + '"' + parameters.skill_name + '"' + """)))
        }
        """)
        
        rows = []
        
        for row in results:
            rows.append(row)
        
        return {"results": rows}
        
    def get_schema(self, parameters: SchemaParameters) -> str:
        """Gets the ontology schema.
        
        Args:
            parameters: Schema parameters (currently unused)
            
        Returns:
            str: The ontology schema in turtle format
        """

        with open("src/core/ontologies/application-level/LinkedInOntology.ttl", "r") as file:
            return file.read()

    def execute_query(self, parameters: QueryParameters) -> Union[str, Dict[str, Any]]:
        """Executes an arbitrary SPARQL query.
        
        Args:
            parameters: Query parameters containing the SPARQL query to execute
            
        Returns:
            Union[str, Dict[str, Any]]: For CONSTRUCT/DESCRIBE queries, returns serialized graph.
                                      For SELECT queries, returns dict with results.
        """
        from lib.abi.utils.Graph import ABIGraph as Graph
        from lib.abi.services.ontology_store.OntologyFactory import OntologyStoreFactory
        from lib.abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
        
        triplestore : IOntologyStoreService = OntologyStoreFactory.OntologyStoreServiceFilesystem("storage/triplestore/People")
        
        print(f"Executing query: {parameters.query}")
        
        results : Graph = triplestore.query(parameters.query)
        
        rows = [row for row in results]
        
        # For CONSTRUCT/DESCRIBE queries, return serialized graph
        return {"results": rows}

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tools
        """
        return [
            StructuredTool(
                name="talent_finder",
                description="Find talent based on specific skills",
                func=lambda **kwargs: self.talent_finder(TalentFinderParameters(**kwargs)),
                args_schema=TalentFinderParameters
            ),
            StructuredTool(
                name="get_schema",
                description="Get the ontology schema in turtle format",
                func=lambda **kwargs: self.get_schema(SchemaParameters(**kwargs)),
                args_schema=SchemaParameters
            ),
            StructuredTool(
                name="execute_query",
                description="Execute an arbitrary SPARQL query against the ontology store. CALL get_schema FIRST TO WRITE A VALID QUERY.",
                func=lambda **kwargs: self.execute_query(QueryParameters(**kwargs)),
                args_schema=QueryParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/talent-finder")
        def find_talent(parameters: TalentFinderParameters):
            return self.talent_finder(parameters)
            
        @router.post("/schema")
        def get_schema(parameters: SchemaParameters):
            return self.get_schema(parameters)
            
        @router.post("/query")
        def execute_query(parameters: QueryParameters):
            return self.execute_query(parameters)

if __name__ == "__main__":
    workflow = HRTalentWorkflow(HRTalentWorkflowConfiguration())
    print(workflow.talent_finder(TalentFinderParameters(skill_name="python")))