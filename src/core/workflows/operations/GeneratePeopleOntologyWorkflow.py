from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import json
import pydash
import yaml

@dataclass
class GeneratePeopleOntologyWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GeneratePeopleOntologyWorkflow.
    
    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the NAAS integration
    """
    naas_integration_config: NaasIntegrationConfiguration

class GeneratePeopleOntologyWorkflowParameters(WorkflowParameters):
    """Parameters for GeneratePeopleOntologyWorkflow.
    
    Attributes:
        workspace_id (str): The ID (UUID) of the naas workspace
    """
    workspace_id: str = Field(..., description="The ID (UUID) of the naas workspace")

class GeneratePeopleOntologyWorkflow(Workflow):
    """Workflow for generating a people ontology from AIA ontologies."""
    __configuration: GeneratePeopleOntologyWorkflowConfiguration
    
    def __init__(self, configuration: GeneratePeopleOntologyWorkflowConfiguration):
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="naas_generate_people_ontology",
            description="Create or update the People Ontology from AIA plugins available in the workspace.",
            func=lambda **kwargs: self.run(GeneratePeopleOntologyWorkflowParameters(**kwargs)),
            args_schema=GeneratePeopleOntologyWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/generate_people_ontology")
        def generate_people_ontology(parameters: GeneratePeopleOntologyWorkflowParameters):
            return self.run(parameters)

    def __get_aia_plugins_ontologies(self, workspace_plugins: list[dict]) -> list[str]:
        aia_plugins_ontologies = []
        
        for plugin in workspace_plugins:
            payload = json.loads(plugin['payload'])
            if payload['slug'].startswith('aia/') and 'ontologies' in payload:
                aia_plugins_ontologies += payload['ontologies']
                
        return aia_plugins_ontologies
    
    def __get_yaml_ontologies(self, ontologies: list[str]) -> list[str]:
        yaml_ontologies = []
        for ontology in ontologies:
            response = self.__naas_integration.get_ontology(self.__configuration.workspace_id, ontology)['ontology']
            yaml_ontologies.append(response['source'])
        return yaml_ontologies
    
    def __merge_yaml_ontologies(self, yaml_ontologies: list[str]) -> str:
        entities = {}
        classes = {}
        loaded_ontologies = pydash.map_(yaml_ontologies, lambda x: yaml.safe_load(x))

        for ontology in loaded_ontologies:
            if 'classes' in ontology:
                for cls in ontology['classes']:
                    if 'id' in cls:
                        classes[cls['id']] = cls

            if 'entities' in ontology:
                for entity in ontology['entities']:
                    if 'id' in entity:
                        if entity['id'] not in entities:
                            entities[entity['id']] = entity
                        else:
                            if 'relations' in entity:
                                if 'relations' not in entities[entity['id']]:
                                    entities[entity['id']]['relations'] = []
                                for relation in entity['relations']:
                                    entities[entity['id']]['relations'].append(relation)

        merged_ontologies = {
            'classes':  pydash.map_(classes),
            'entities': pydash.map_(entities)
        }

        merged_ontologies_yaml = yaml.safe_dump(merged_ontologies)
        
        return merged_ontologies_yaml
    
    def run(self, parameters: GeneratePeopleOntologyWorkflowParameters) -> str:
        # Get all plugins from the workspace
        print('Getting plugins')
        workspace_plugins = self.__naas_integration.get_plugins(parameters.workspace_id)['workspace_plugins']
        
        # Get all ontologies from the AIA plugins
        print('Getting AIA plugins ontologies')
        aia_plugins_ontologies = self.__get_aia_plugins_ontologies(workspace_plugins)
        
        # Get the YAML source code for each ontology
        print('Getting YAML ontologies')
        yaml_ontologies = self.__get_yaml_ontologies(aia_plugins_ontologies)
        
        # Merge the ontologies
        print('Merging ontologies')
        merged_ontologies_yaml = self.__merge_yaml_ontologies(yaml_ontologies)
        
        # List ontologies to find the people ontology
        print('Getting ontologies')
        ontologies = self.__naas_integration.get_ontologies(parameters.workspace_id)['ontologies']
        
        # Find the people ontology
        print('Finding the people ontology')
        people_ontology = next((ontology for ontology in ontologies if ontology['label'] == 'Peoples - Test'), None)
        
        if people_ontology is None:
            print('Creating the people ontology')
            people_ontology = self.__naas_integration.create_ontology(parameters.workspace_id, 'Peoples - Test', merged_ontologies_yaml, 'USE_CASE')
        else:
            print('Updating the people ontology')
            self.__naas_integration.update_ontology(parameters.workspace_id, people_ontology['id'], merged_ontologies_yaml, 'USE_CASE')
            
        return "People ontology generated"
