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
class GetPersonSkillsConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for GetPersonSkills workflow.
    
    Attributes:
        ontology_store (IOntologyStoreService): Ontology store service
    """
    ontology_store: IOntologyStoreService

class GetPersonSkillsWorkflowParameters(WorkflowParameters):
    """Parameters for GetPersonSkills workflow.
    
    Attributes:
        person_name (str): Person name
    """
    person_name: str = Field(..., description="Name of the person to search skills of")

class GetSkillsPersonWorkflowParameters(WorkflowParameters):
    """Parameters for GetSkillsPerson workflow.
    
    Attributes:
        skill_label (str): Skill label
    """
    skill_label: str = Field(..., description="Label of the skill to search persons having it")

class GetPersonSkillsWorkflow(Workflow):
    """Workflow for getting person skills from the ontology."""
    __configuration: GetPersonSkillsConfigurationWorkflow
    
    def __init__(self, configuration: GetPersonSkillsConfigurationWorkflow):
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

    def get_person_skills(self, parameters: GetPersonSkillsWorkflowParameters) -> dict:
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
        results = self.__configuration.ontology_store.query(query)
        return self.results_to_list(results)
    
    def get_skill_persons(self, parameters: GetSkillsPersonWorkflowParameters) -> dict:
        query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX cco: <https://www.commoncoreontologies.org/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        SELECT DISTINCT ?person_label
        WHERE {{
            ?skill a owl:NamedIndividual ;
                    rdfs:label "{parameters.skill_label}" ;
                    abi:isSkillOf ?person .
            ?person rdfs:label ?person_label .
        }}
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
                name="get_person_skills",
                description="Get skills of a person from the ontology.",
                func=lambda person_name: self.get_person_skills(GetPersonSkillsWorkflowParameters(person_name=person_name)),
                args_schema=GetPersonSkillsWorkflowParameters
            ),
            StructuredTool(
                name="get_skill_persons",
                description="Get persons having the skill from the ontology.",
                func=lambda skill_label: self.get_skill_persons(GetSkillsPersonWorkflowParameters(skill_label=skill_label)),
                args_schema=GetSkillsPersonWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass