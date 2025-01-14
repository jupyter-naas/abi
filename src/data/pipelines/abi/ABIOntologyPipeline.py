from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from abi import logger
from dataclasses import dataclass
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi.utils.Graph import ABIGraph, ABI, BFO
from abi.utils.OntologyYaml import OntologyYaml
from rdflib import Graph, RDFS, OWL, DC, URIRef
from rdflib.namespace import Namespace
from pathlib import Path
import importlib
import inspect
import pydash as _
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
import re
import glob

@dataclass
class ABIOntologyConfiguration(PipelineConfiguration):
    """Configuration for ABIOntology pipeline.
    
    Attributes:
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use
    """
    naas_integration_config: NaasIntegrationConfiguration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "abi-ontology"


class ABIOntologyParameters(PipelineParameters):
    """Parameters for ABIOntology pipeline execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to publish the ontology to.
        label (str): The label of the ontology.
        description (str): The description of the ontology.
        logo_url (str): The logo URL of the ontology.
    """
    workspace_id: str
    label: str = "ABI Ontology"
    description: str = "Represents ABI Ontology."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    
class ABIOntologyPipeline(Pipeline):
    """Pipeline for collecting and organizing ABI components into an ontology."""
    
    __configuration: ABIOntologyConfiguration
    
    def __init__(self, configuration: ABIOntologyConfiguration):
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def __generate_coordinates(self, radius, num_points, initial_angle=210):
        import math
        coordinates = []
        for i in range(num_points):
            angle = math.radians(initial_angle + i*(360/num_points))
            x = round(radius * math.cos(angle))
            y = round(radius * math.sin(angle))
            coordinates.append((x, y))
        return coordinates

    def __scan_integrations(self, graph: Graph) -> None:
        """Scan integrations and add to graph."""
        integrations_dir = Path("src/integrations")
        nb_integrations = len(glob.glob("src/integrations/*.py", recursive=True)) - 1
        logger.info(f"Found {nb_integrations} integrations")
        coordinates = self.__generate_coordinates(1100, nb_integrations)
        i = 0

        for file in sorted(integrations_dir.glob("*.py")):
            if "__IntegrationTemplate__" in str(file):
                continue
            if file.stem.endswith("Integration"):
                try:
                    module = importlib.import_module(f"src.integrations.{file.stem}")
                    class_name = file.stem
                    if hasattr(module, class_name):
                        integration_class = getattr(module, class_name)
                        doc = inspect.getdoc(integration_class) or ""
                        logo_url = getattr(module, "LOGO_URL", "")

                    # Add integration entry
                    graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=str(file.stem),
                        label=file.stem.replace("Integration", ""),
                        is_a=ABI.Integration,
                        description=doc,
                        logo=logo_url,
                        ontology_group="Integrations",
                        x=coordinates[i][0],
                        y=coordinates[i][1],
                    )
                    i += 1

                except ImportError as e:
                    logger.error(f"Error importing integration {file.stem}: {e}")

    def __scan_ontologies(self, graph: Graph) -> None:
        """Scan domain-level ontologies and add to graph."""
        ontologies_dir = Path("src/ontologies/")
        nb_ontologies = len(glob.glob("src/ontologies/**/*.ttl", recursive=True)) - len(glob.glob("src/ontologies/application-level/*.ttl", recursive=True)) - 2
        logger.info(f"Found {nb_ontologies} ontologies")
        coordinates = self.__generate_coordinates(650, nb_ontologies)
        i = 0
        
        for file in ontologies_dir.rglob("*.ttl"):
            if "__OntologyTemplate__" in str(file) or "ConsolidatedOntology" in str(file) or "application-level" in str(file):
                continue
            try:
                g = Graph()
                g.parse(file, format="turtle")

                # # Get ontology title
                # # Try to get title from DC.title
                # dc_title = next(g.objects(None, DC.title), None)
                # logger.debug(f"DC.title: {dc_title}")

                # # If not found, try OWL.Ontology
                # owl_ontology = next(g.objects(None, OWL.Ontology), None) if not dc_title else None
                # logger.debug(f"OWL.Ontology: {owl_ontology}")

                # # If still not found, try RDFS.label
                # rdfs_label = next(g.objects(None, RDFS.label), "") if not (dc_title or owl_ontology) else None
                # logger.debug(f"RDFS.label: {rdfs_label}")

                # # Use first non-None value
                # ontology_title = dc_title or owl_ontology or rdfs_label or ""
                ontology_title = str(file.stem).replace("Ontology", "").replace("-", " ").title()
                logger.info(f"Ontology title: {ontology_title}")

                # Get ontology type from file path
                is_top_level = "top-level" in str(file)
                is_mid_level = "mid-level" in str(file)
                is_domain = "domain-level" in str(file)
                is_application = "application-level" in str(file)
                
                # Set image URL based on ontology type
                if is_top_level:
                    image_url = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/2b9ac8af-4026-4173-8796-1c2de5d34966/images/2dd774ba51a94b4eb4d29d444e7771cc"
                    source_title = "BFO"
                elif is_mid_level:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_CCO.png"
                    source_title = "CCO"
                elif is_domain:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
                    source_title = "Domain Ontology"
                elif is_application:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
                    source_title = "Application Ontology"
                else:
                    image_url = ""
                    source_title = "Unknown"
                    
                # Add ontology entry
                ontology = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=str(file.stem),
                    label=ontology_title,
                    is_a=ABI.Ontology,
                    description=next(g.objects(None, DC.description), "No description provided.") + ("" if str(next(g.objects(None, DC.description), "No description provided.")).endswith(".") else "."),
                    logo=image_url,
                    type=source_title,
                    ontology_group="Ontologies",
                    x=coordinates[i][0],
                    y=coordinates[i][1],
                )
                i += 1

            except Exception as e:
                logger.error(f"Error processing ontology {file}: {e}")

    def __scan_assistants(self, graph: Graph) -> None:
        """Scan assistants directory and add to graph, excluding experts/integrations."""
        assistants_dir = Path("src/assistants")
        nb_assistants = len(glob.glob("src/assistants/domain/*.py", recursive=True)) + len(glob.glob("src/assistants/foundation/*.py", recursive=True))
        logger.info(f"Found {nb_assistants} assistants")
        coordinates = self.__generate_coordinates(350, nb_assistants - 1)
        i = 0

        for file in assistants_dir.rglob("*.py"):
            if "__AssistantTemplate__" in str(file) or "expert" in str(file).lower() or "integration" in str(file).lower():
                continue
            if file.stem.endswith("Assistant"):
                try:
                    # Build import path based on file location
                    import_path = "src.assistants"
                    relative_path = file.relative_to(assistants_dir)
                    if len(relative_path.parts) > 1:
                        # File is in subfolder(s)
                        import_path += "." + ".".join(relative_path.parts[:-1])
                    import_path += f".{file.stem}"
                    
                    module = importlib.import_module(import_path)
                    title = (file.stem.replace("Assistant", " ")) + "Assistant"
                    slug = title.lower().replace(" ", "-").replace("_", "-")
                    if "Supervisor" in (file.stem):
                        x = 0
                        y = 0
                    else:
                        x = coordinates[i][0]
                        y = coordinates[i][1]
                    
                    assistant = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=str(file.stem),
                        label=file.stem,
                        is_a=ABI.Assistant,
                        description=getattr(module, "DESCRIPTION", ""),
                        avatar=getattr(module, "AVATAR_URL", ""),
                        prompt=getattr(module, "SYSTEM_PROMPT", ""),
                        prompt_type="system",
                        slug=slug,
                        ontology_group="Assistants",
                        x=x,
                        y=y,
                    )
                    i += 1

                    # Find integrations used in the assistant
                    with open(file, 'r') as f:
                        content = f.read()
                    #     # Look for imports from src.integrations
                    #     integration_imports = re.findall(r'from src\.integrations\.(\w+)', content)
                    #     logger.info(f"Found {len(integration_imports)} integrations in {file.stem}")
                    #     for integration in integration_imports:
                    #         integration_uri = URIRef(str(ABI.Integration) + "#" + str(integration))
                    #         logger.info(f"Adding relation between assistant and integration {integration_uri}")
                    #         # Add relation between assistant and integration
                    #         graph.add((assistant, ABI.integratesWith, integration_uri))

                        # Look for import from src.assistants
                        assistant_imports = re.findall(r'from src\.assistants(?:\.\w+)*\.(\w+Assistant)', content)
                        logger.info(f"Found {len(assistant_imports)} assistants in {file.stem}")
                        for a in assistant_imports:
                            assistant_uri = graph.add_individual_to_prefix(
                                prefix=ABI,
                                uid=str(a),
                                label=a,
                                is_a=ABI.Assistant,
                            )
                            logger.info(f"Adding relation between assistant {assistant} and assistant {assistant_uri}")
                            graph.add((assistant, ABI.communicatesWithAssistant, assistant_uri))

                except ImportError as e:
                    logger.error(f"Error importing assistant {file.stem}: {e}")

    def run(self, parameters: ABIOntologyParameters) -> Graph:
        """Executes the pipeline to create the ABI ontology.
        
        Args:
            parameters (ABIOntologyParameters): Pipeline parameters
            
        Returns:
            Graph: The resulting RDF graph
        """
        graph = ABIGraph()
        
        # # Add ABI
        # workspace = graph.add_individual_to_prefix(
        #     prefix=ABI,
        #     uid="DemoWorkspace",
        #     label="ABI Demo",
        #     is_a=ABI.NaasWorkspace,
        #     ontology_group="Workspace"
        # )

        # Scan and add components
        logger.debug(f"Scanning integrations")
        self.__scan_integrations(graph)
        logger.debug(f"Scanning ontologies")
        self.__scan_ontologies(graph)
        logger.debug(f"Scanning assistants")
        self.__scan_assistants(graph)
        
        # Store the graph
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)

        mapping_colors = {
            'http://ontology.naas.ai/abi/NaasWorkspace': '#47DD82',
            'http://ontology.naas.ai/abi/Assistant': 'orange', 
            'http://ontology.naas.ai/abi/Ontology': 'grey',
            'http://ontology.naas.ai/abi/Integration': 'grey',
        }
        # Generate YAML data with mapping colors
        yaml_data = OntologyYaml.rdf_to_yaml(graph, class_colors_mapping=mapping_colors)

        # Initialize parameters
        workspace_id = parameters.workspace_id
        onto_label = parameters.label
        onto_description = parameters.description
        onto_logo_url = parameters.logo_url
    
        # Save records to local file for backup
        import os
        import json
        from datetime import datetime
        import yaml
        from yaml import Dumper, Loader
        
        # Create backup directory if it doesn't exist
        backup_dir = "src/data/ontology-yaml"
        os.makedirs(backup_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"ontology_yaml_{timestamp}.yaml")

        # Convert to YAML format and save
        with open(backup_file, "w", encoding="utf-8") as f:
            yaml_str = yaml.dump(yaml_data, Dumper=Dumper)
            f.write(yaml_str)
            
        # Load and parse YAML back
        with open(backup_file, "r", encoding="utf-8") as f:
            yaml_data = yaml.load(f, Loader=Loader)
        logger.info(f"Saved and loaded to {backup_file}")

        # Push ontology to workspace if API key provided
        try:
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
                    level="USE_CASE",
                    description=onto_description,
                    logo_url=onto_logo_url
                )
                ontology_id = _.get(res, "ontology.id")
                logger.info(f"✅ Ontology '{ontology_id}' successfully created.")
            else:
                # Update existing ontology
                res = self.__naas_integration.update_ontology(
                    workspace_id=workspace_id,
                    ontology_id=ontology_id,
                    source=yaml.dump(yaml_data, Dumper=Dumper),
                    level="USE_CASE",
                    description=onto_description,
                    logo_url=onto_logo_url
                )
                logger.info(f"✅ Ontology '{ontology_id}' successfully updated.")

        except Exception as e:
            logger.error(f"Error pushing ontology to workspace: {e}")
            raise e
            

        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="abi_ontology_pipeline",
                description="Creates an ontology of ABI components and their relationships",
                func=lambda **kwargs: self.run(ABIOntologyParameters(**kwargs)),
                args_schema=ABIOntologyParameters
            )
        ]  

    def as_api(
            self, 
            router: APIRouter,
            route_name: str = "abiontology",
            name: str = "ABI Ontology",
            description: str = "Creates an ontology of ABI components and their relationships",
            tags: list[str] = []
        ) -> None:
        """Adds API endpoints for this pipeline to the given router."""
        @router.post(f"/{route_name}", name=name, description=description, tags=tags)
        def run(parameters: ABIOntologyParameters):
            return self.run(parameters).serialize(format="turtle") 

if __name__ == "__main__":
    from src import secret, config
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    from abi.services.ontology_store.OntologyStoreService import OntologyStoreService

    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))

    pipeline = ABIOntologyPipeline(ABIOntologyConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=secret.get("NAAS_API_KEY")
        ),
        ontology_store=ontology_store
    ))
    pipeline.run(ABIOntologyParameters(workspace_id="96ce7ee7-e5f5-4bca-acf9-9d5d41317f81"))