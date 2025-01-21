from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any
from rdflib import Graph
from abi.utils.OntologyYaml import OntologyYaml
import yaml
from yaml import Dumper
from abi.utils.Graph import ABIGraph, ABI, BFO
from typing import Dict
import pydash as _

@dataclass
class CreateOntologyYAMLConfiguration(WorkflowConfiguration):
    """Configuration for CreateOntologyYAML workflow.
    
    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """
    naas_integration_config: NaasIntegrationConfiguration
    ontology_store: IOntologyStoreService

class CreateOntologyYAMLParameters(WorkflowParameters):
    """Parameters for CreateOntologyYAML workflow execution.
    
    Attributes:
        ontology_name (str): The name of the ontology store to use
        label (str): The label of the ontology
        description (str): The description of the ontology
        logo_url (str): The URL of the ontology logo
        level (str): The level of the ontology (e.g., 'TOP_LEVEL', 'MID_LEVEL', 'DOMAIN', 'USE_CASE')
        display_relations_names (bool): Whether to display relation names in the visualization
    """
    ontology_name: str = Field(..., description="The name of the ontology store to use")
    label: str = Field(..., description="The label of the ontology")
    description: str = Field(..., description="The description of the ontology. Example: 'Represents ABI Ontology with assistants, workflows, ontologies, pipelines and integrations.'")
    workspace_id: str = Field(..., description="The ID of the Naas workspace to use")
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
    level: str ='USE_CASE'
    display_relations_names: bool = True
    class_colors_mapping: Dict[str, str] = {}

class CreateOntologyYAML(Workflow):
    """Workflow for converting ontology files to YAML and pushing them to a Naas workspace."""
    
    __configuration: CreateOntologyYAMLConfiguration
    
    def __init__(self, configuration: CreateOntologyYAMLConfiguration):
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def graph_to_yaml(self, parameters: CreateOntologyYAMLParameters) -> Any:
        # Push ontology to workspace if API key provided
        try:
            # Init graph
            graph = self.__configuration.ontology_store.get(parameters.ontology_name)

            # Convert to YAML
            yaml_data = OntologyYaml.rdf_to_yaml(
                graph, 
                display_relations_names=parameters.display_relations_names,
                class_colors_mapping=parameters.class_colors_mapping
            )
            # Initialize parameters
            workspace_id = parameters.workspace_id
            onto_label = parameters.label
            onto_description = parameters.description
            onto_logo_url = parameters.logo_url
            onto_level = parameters.level

            # Get ontology ID if it exists
            ontologies = self.__naas_integration.get_ontologies(workspace_id).get("ontologies", [])
            ontology_id = None
            for ontology in ontologies:
                if ontology.get("label") == onto_label:
                    ontology_id = ontology.get("id")
                    break

            if ontology_id is None:
                # Create new ontology
                res = self.__naas_integration.create_ontology(
                    workspace_id=workspace_id,
                    label=onto_label,
                    source=yaml.dump(yaml_data, Dumper=Dumper),
                    level=onto_level,
                    description=onto_description,
                    logo_url=onto_logo_url,
                )
                ontology_id = _.get(res, "ontology.id")
                message = f"✅ Ontology '{ontology_id}' successfully created."
                logger.info(message)
            else:
                # Update existing ontology
                res = self.__naas_integration.update_ontology(
                    workspace_id=workspace_id,
                    ontology_id=ontology_id,
                    source=yaml.dump(yaml_data, Dumper=Dumper),
                    level=onto_level,
                    description=onto_description,
                    logo_url=onto_logo_url,
                )
                message = f"✅ Ontology '{ontology_id}' successfully updated."
                logger.info(message)

        except Exception as e:
            message = f"Error pushing ontology to workspace: {e}"
            logger.error(message)
        return message

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="create_ontology_yaml",
                description="Convert an ontology file to YAML and push it to a Naas workspace",
                func=lambda **kwargs: self.graph_to_yaml(CreateOntologyYAMLParameters(**kwargs)),
                args_schema=CreateOntologyYAMLParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
        
if __name__ == "__main__":
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
    import argparse
    from src.mappings import COLORS_NODES

    # Create argument parser
    parser = argparse.ArgumentParser(description='Create or update ontology YAML')
    parser.add_argument('--ontology_name', required=True, help='Name of the ontology store to use')
    parser.add_argument('--label', required=True, help='Label of the ontology')
    parser.add_argument('--description', required=True, help='Description of the ontology')

    # Initialize configurations
    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))
    naas_integration_config = NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
    
    # Initialize the workflow
    workflow = CreateOntologyYAML(CreateOntologyYAMLConfiguration(
        naas_integration_config=naas_integration_config,
        ontology_store=ontology_store
    ))

    # Run the workflow
    workflow.graph_to_yaml(
        CreateOntologyYAMLParameters(
            ontology_name="github",
            label="Github Ontology",
            description="Represents Github Application Ontology with issues, repositories, projects and pull requests.",
            workspace_id=config.workspace_id,
            class_colors_mapping=COLORS_NODES
        )
    )