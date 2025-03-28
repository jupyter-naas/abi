from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret, config, services
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any
from abi.utils.OntologyYaml import OntologyYaml
import yaml
from yaml import Dumper
from typing import Dict
from abi.services.ontology_store.OntologyStorePorts import OntologyEvent
import pydash as _
from rdflib import Graph

@dataclass
class CreateClassOntologyYAMLConfiguration(WorkflowConfiguration):
    """Configuration for CreateOntologyYAML workflow.
    
    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """
    naas_integration_config: NaasIntegrationConfiguration
    ontology_store: IOntologyStoreService

class CreateClassOntologyYAMLParameters(WorkflowParameters):
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
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
    level: str ='USE_CASE'
    display_relations_names: bool = True
    class_colors_mapping: Dict[str, str] = {}

class CreateClassOntologyYAML(Workflow):
    """Workflow for converting ontology files to YAML and pushing them to a Naas workspace."""
    
    __configuration: CreateClassOntologyYAMLConfiguration

    def __init__(self, configuration: CreateClassOntologyYAMLConfiguration):
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def trigger(self, event: OntologyEvent, ontology_name:str, triple: tuple[Any, Any, Any]) -> Graph:
        s, p, o = triple
        logger.info(f"==> Triggering Create Class Ontology YAML Workflow: {s} {p} {o}, 'ontology_name': {ontology_name}")
        if str(event) == str(OntologyEvent.INSERT) and (str(o) == "http://www.w3.org/2002/07/owl#NamedIndividual" or str(p) == "http://ontology.naas.ai/abi/isSkillOf" or str(p) == "http://ontology.naas.ai/abi/hasSkill"):
            label = " ".join(ontology_name.split("_")[:-1]).capitalize()
            description = f"Ontology for {label}"
            return self.graph_to_yaml(CreateClassOntologyYAMLParameters(
                ontology_name=ontology_name,
                label=label,
                description=description,
            ))
        return None

    def graph_to_yaml(self, parameters: CreateClassOntologyYAMLParameters) -> str:
        # Initialize parameters
        yaml_data = None
        graph = self.__configuration.ontology_store.get(parameters.ontology_name)

        # Get all object properties uri
        query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT DISTINCT ?object
        WHERE {
        # Find all predicates used in triples
        ?subject ?predicate ?object .
        
        # Only get predicates that are object properties and in URI reference format
        FILTER(isURI(?object))
        
        # Exclude RDF type triples
        FILTER(?predicate != rdf:type)
        }
        ORDER BY ?object
        """
        list_uri = [str(object.get("object")) for object in graph.query(query)]

        # Get all object properties label and type
        if len(list_uri) > 0:
            uri_filter = "(" + " || ".join([f"?object = <{uri}>" for uri in list_uri]) + ")"
            query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT DISTINCT ?object ?label ?type
            WHERE {{
            ?object rdfs:label ?label .
            ?object rdf:type ?type .
            FILTER {uri_filter}
            }}
            ORDER BY ?object
            """
            results = services.ontology_store_service.query(query)

            # Add object properties to graph
            from rdflib import URIRef, RDFS, Literal, RDF, OWL
            for row in results:
                graph.add((URIRef(row.get("object")), RDF.type, URIRef(row.get("type"))))
                graph.add((URIRef(row.get("object")), RDF.type, OWL.NamedIndividual))
                graph.add((URIRef(row.get("object")), RDFS.label, Literal(row.get("label"))))

        # Upload asset to Naas
        asset = self.__naas_integration.upload_asset(
            data=graph.serialize(format="turtle").encode('utf-8'),  # Convert to bytes
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix="assets",
            object_name=str(parameters.ontology_name + ".ttl"),
            visibility="public"
        )
        # Save asset URL to JSON
        asset_url = asset.get("asset").get("url")
        if asset_url.endswith("/"):
            asset_url = asset_url[:-1]

        # Convert to YAML
        try:
            yaml_data = OntologyYaml.rdf_to_yaml(
                graph, 
                display_relations_names=parameters.display_relations_names,
                class_colors_mapping=parameters.class_colors_mapping
            )
        except Exception as e:
            message = f"Error converting ontology to YAML: {e}"

        # Initialize parameters
        if yaml_data is not None:
            workspace_id = config.workspace_id
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
                    download_url=asset_url,
                    logo_url=onto_logo_url,
                )
                ontology_id = _.get(res, "ontology.id")
                message = f"✅ Ontology '{ontology_id}' successfully created."
            else:
                # Update existing ontology
                res = self.__naas_integration.update_ontology(
                    workspace_id=workspace_id,
                    ontology_id=ontology_id,
                    source=yaml.dump(yaml_data, Dumper=Dumper),
                    level=onto_level,
                    description=onto_description,
                    download_url=asset_url,
                    logo_url=onto_logo_url,
                )
                message = f"✅ Ontology '{ontology_id}' successfully updated."
        logger.info(message)
        return ontology_id

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="ontology_create_yaml",
                description="Convert an ontology file to YAML and push it to Naas workspace.",
                func=lambda **kwargs: self.graph_to_yaml(CreateClassOntologyYAMLParameters(**kwargs)),
                args_schema=CreateClassOntologyYAMLParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass