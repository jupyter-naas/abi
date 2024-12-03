from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
import json
import pydash
import yaml

@dataclass
class GeneratePeopleOntologyWorkflowConfiguration(WorkflowConfiguration):
    workspace_id : str

class GeneratePeopleOntologyWorkflow(Workflow):
    __configuration: GeneratePeopleOntologyWorkflowConfiguration
    
    def __init__(self, configuration: GeneratePeopleOntologyWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__naas_integration = NaasIntegration(
            NaasIntegrationConfiguration(api_key=secret.get('NAAS_API_KEY'))
        )

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
    
    def run(self) -> str:
        # Get all plugins from the workspace
        print('Getting plugins')
        workspace_plugins = self.__naas_integration.get_plugins(self.__configuration.workspace_id)['workspace_plugins']
        
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
        ontologies = self.__naas_integration.get_ontologies(self.__configuration.workspace_id)['ontologies']
        
        # Find the people ontology
        print('Finding the people ontology')
        people_ontology = next((ontology for ontology in ontologies if ontology['label'] == 'Peoples - Test'), None)
        
        if people_ontology is None:
            print('Creating the people ontology')
            people_ontology = self.__naas_integration.create_ontology(self.__configuration.workspace_id, 'Peoples - Test', merged_ontologies_yaml, 'USE_CASE')
        else:
            print('Updating the people ontology')
            self.__naas_integration.update_ontology(self.__configuration.workspace_id, people_ontology['id'], merged_ontologies_yaml, 'USE_CASE')
            
        return "People ontology generated"
                
        
        

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.get("/generate_people_ontology")
    def generate_people_ontology():
        configuration = GeneratePeopleOntologyWorkflowConfiguration()
        workflow = GeneratePeopleOntologyWorkflow(configuration)
        return workflow.run()
    
    uvicorn.run(app, host="0.0.0.0", port=9877)  # Note: Using different port from github workflow

def main():
    workspace_id = '59d41231-e6c2-498f-9f2b-77c564a7e45f'
    
    configuration = GeneratePeopleOntologyWorkflowConfiguration(workspace_id=workspace_id)
    workflow = GeneratePeopleOntologyWorkflow(configuration)
    turtle = workflow.run()
    print(turtle)

def as_tool():
    from langchain_core.tools import StructuredTool
    
    def generate_people_ontology(workspace_id: str):
        print(f"Generating people ontology for workspace {workspace_id}")
        configuration = GeneratePeopleOntologyWorkflowConfiguration(workspace_id=workspace_id)
        workflow = GeneratePeopleOntologyWorkflow(configuration)
        return workflow.run()
    
    
    class GeneratePeopleOntologyToolSchema(BaseModel):
        workspace_id: str = Field(..., description="The ID (UUID) of the naas workspace.")
    
    return StructuredTool(
        name="naas_generate_people_ontology",
        description="Generate the ontology of people in naas.",
        func=lambda workspace_id: generate_people_ontology(workspace_id),
        args_schema=GeneratePeopleOntologyToolSchema
    )

if __name__ == "__main__":
    main()
