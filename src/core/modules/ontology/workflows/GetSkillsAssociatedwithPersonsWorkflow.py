from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
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
from abi.utils.SPARQL import results_to_list

@dataclass
class GetSkillsAssociatedwithPersonsConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for GetSkillsAssociatedwithPersons workflow.
    
    Attributes:
        triple_store (ITripleStoreService): Ontology store service
    """
    triple_store: ITripleStoreService

class GetSkillsAssociatedwithPersonsWorkflowParameters(WorkflowParameters):
    """Parameters for GetSkillsAssociatedwithPersons workflow.
    
    Attributes:
        person_name (str): Person name
    """
    person_name: str = Field(..., description="Name of the person to search skills of")

class GetSkillsAssociatedwithPersonsWorkflow(Workflow):
    """Workflow for getting person skills from the ontology."""
    __configuration: GetSkillsAssociatedwithPersonsConfigurationWorkflow
    
    def __init__(self, configuration: GetSkillsAssociatedwithPersonsConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_skills_associated_with_persons(self, parameters: GetSkillsAssociatedwithPersonsWorkflowParameters) -> dict:
        query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX cco: <https://www.commoncoreontologies.org/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        SELECT DISTINCT ?skill_label
        WHERE {{
            ?person a owl:NamedIndividual ;
                    rdfs:label "{parameters.person_name}" ;
                    abi:hasSkill ?skill .
            ?skill rdfs:label ?skill_label .
        }}
        """
        results = self.__configuration.triple_store.query(query)
        return results_to_list(results)
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="get_skills_associated_with_persons",
                description="Get skills associated with a person from the ontology.",
                func=lambda person_name: self.get_skills_associated_with_persons(GetSkillsAssociatedwithPersonsWorkflowParameters(person_name=person_name)),
                args_schema=GetSkillsAssociatedwithPersonsWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass