from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from abi import logger
from dataclasses import dataclass
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi.utils.Graph import ABIGraph, ABI, BFO
from abi.utils.OntologyYaml import OntologyYaml
from rdflib import Graph, RDFS, OWL, DC, URIRef, RDF
from rdflib.namespace import Namespace
from pathlib import Path
import importlib
import inspect
import pydash as _
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
import re
import glob
import os
from datetime import datetime
import yaml
from yaml import Dumper, Loader

@dataclass
class AbiApplicationPipelineConfiguration(PipelineConfiguration):
    """Configuration for ABIOntology pipeline.
    
    Attributes:
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use
    """
    naas_integration_config: NaasIntegrationConfiguration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "application/abi-boilerplate"

class OntologyPipelineParameters(PipelineParameters):
    """Parameters for ABIOntology pipeline execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to publish the ontology to.
        label (str): The label of the ontology.
        description (str): The description of the ontology.
        logo_url (str): The logo URL of the ontology.
        level (str): The level of the ontology.
    """
    workspace_id: str = "96ce7ee7-e5f5-4bca-acf9-9d5d41317f81"
    label: str = "ABI Ontology"
    description: str = "Represents ABI Ontology with assistants, workflows, ontologies, pipelines and integrations."
    logo_url: str = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    level: str = "USE_CASE"

class AbiApplicationPipeline(Pipeline):
    """Pipeline for collecting and organizing ABI components into an ontology."""
    
    __configuration: AbiApplicationPipelineConfiguration
    
    def __init__(self, configuration: AbiApplicationPipelineConfiguration):
        super().__init__(configuration)
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

    def scan_integrations(self, graph: Graph) -> None:
        """Scan integrations and add to graph."""
        integrations_dir = Path("src/integrations")
        nb_integrations = len(glob.glob("src/integrations/*.py", recursive=True)) - 1
        logger.debug(f"---> Found {nb_integrations} integrations.")
        coordinates = self.__generate_coordinates(900, nb_integrations)
        
        from src.mappings import ASSISTANTS_INTEGRATIONS
        # Create mapping of integration to order based on ASSISTANTS_INTEGRATIONS
        integrations_order = {}
        order = 0
        for integrations in ASSISTANTS_INTEGRATIONS.values():
            for integration in integrations:
                if integration not in integrations_order:
                    integrations_order[integration] = order
                    order += 1

        for file in integrations_dir.glob("*.py"):
            if "__IntegrationTemplate__" in str(file):
                continue
            if file.stem.endswith("Integration"):
                try:
                    i = integrations_order.get(str(file.stem), None)
                    if i is None:
                        i = order
                        order += 1
                    x = coordinates[i][0]
                    y = coordinates[i][1]

                    module = importlib.import_module(f"src.core.integrations.{file.stem}")
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
                        x=x,
                        y=y,
                    )
                    i += 1

                except ImportError as e:
                    logger.error(f"Error importing integration {file.stem}: {e}")

    def scan_ontologies(self, graph: Graph) -> None:
        """Scan domain-level ontologies and add to graph."""
        ontologies_dir = Path("src/ontologies/domain-level")
        nb_ontologies = len(list(ontologies_dir.glob("*.ttl")))
        logger.debug(f"---> Found {nb_ontologies} ontologies.")
        coordinates = self.__generate_coordinates(500, nb_ontologies)

        from src.mappings import ASSISTANTS_ONTOLOGIES
        # Create mapping of ontology to order based on ASSISTANTS_ONTOLOGIES
        ontologies_order = {}
        order = 0
        for ontologies in ASSISTANTS_ONTOLOGIES.values():
            for ontology in ontologies:
                if ontology not in ontologies_order:
                    ontologies_order[ontology] = order
                    order += 1
        
        for file in ontologies_dir.glob("*.ttl"):
            if "__OntologyTemplate__" in str(file) or "ConsolidatedOntology" in str(file):
                continue
            try:
                i = ontologies_order.get(str(file.stem), None)
                if i is None:
                    i = order
                    order += 1
                x = coordinates[i][0]
                y = coordinates[i][1]

                g = Graph()
                g.parse(file, format="turtle")

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
                    label=str(file.stem).replace("Ontology", "").replace("-", " ").title(),
                    is_a=ABI.Ontology,
                    description=next(g.objects(None, DC.description), "No description provided.") + ("" if str(next(g.objects(None, DC.description), "No description provided.")).endswith(".") else "."),
                    type=source_title,
                    ontology_group="Ontologies",
                    x=coordinates[i][0],
                    y=coordinates[i][1],
                )
                i += 1

            except Exception as e:
                logger.error(f"Error processing ontology {file}: {e}")

    def scan_assistants(self, graph: Graph) -> None:
        """Scan assistants directory and add to graph, excluding experts/integrations."""
        assistants_dir = Path("src/assistants")
        nb_assistants = len(glob.glob("src/assistants/domain/*.py", recursive=True)) + len(glob.glob("src/assistants/foundation/*.py", recursive=True))
        logger.debug(f"---> Found {nb_assistants} assistants.")
        coordinates = self.__generate_coordinates(200, nb_assistants - 2) # Exclude supervisor assistant
        i = 0

        for file in assistants_dir.rglob("*.py"):
            if "__AssistantTemplate__" in str(file) or "expert" in str(file).lower() or "integration" in str(file).lower():
                continue
            if file.stem.endswith("Assistant"):
                try:
                    # Build import path based on file location
                    import_path = "src.core.assistants"
                    relative_path = file.relative_to(assistants_dir)
                    if len(relative_path.parts) > 1:
                        # File is in subfolder(s)
                        import_path += "." + ".".join(relative_path.parts[:-1])
                    import_path += f".{file.stem}"
                    
                    module = importlib.import_module(import_path)

                    def get_assistant_metadata(file_stem: str, module, coordinates: list):
                        """Get the coordinates and avatar for an assistant based on its type.
                        
                        Args:
                            file_stem (str): The stem of the assistant file
                            module: The imported assistant module
                            coordinates (list): List of coordinate tuples
                        """
                        title = (file_stem.replace("Assistant", " ")) + "Assistant"
                        slug = title.lower().replace(" ", "-").replace("_", "-")
                        description = getattr(module, "DESCRIPTION", "")
                        prompt = getattr(module, "SYSTEM_PROMPT", "")
                        avatar = None
                        if "Supervisor" in file_stem:
                            avatar = getattr(module, "AVATAR_URL", "")
                            x = -50
                            y = 25
                        elif "Support" in file_stem:
                            avatar = getattr(module, "AVATAR_URL", "")
                            x = 50
                            y = -25
                        else:
                            from src.mappings import ASSISTANTS_ORDER
                            i = ASSISTANTS_ORDER.get(str(file_stem))
                            x = coordinates[i][0]
                            y = coordinates[i][1]
                        return title, slug, description, prompt, avatar, x, y
                    
                    # Create assistant if it doesn't exist
                    assistant = URIRef(str(ABI.Assistant) + "#" + file.stem)
                    if (assistant, RDF.type, OWL.NamedIndividual) not in graph:
                        title, slug, description, prompt, avatar, x, y = get_assistant_metadata(file.stem, module, coordinates)
                        assistant = graph.add_individual_to_prefix(
                            prefix=ABI,
                            uid=str(file.stem),
                            label=title,
                            is_a=ABI.Assistant,
                            description=description,
                            avatar=avatar,
                            prompt=prompt,
                            slug=slug,
                            ontology_group="Assistants",
                            x=x,
                            y=y,
                        )
                    else:
                        logger.debug(f"Assistant {file.stem} already exists.")

                    # Find components used in the assistant
                    with open(file, 'r') as f:
                        content = f.read()

                        # Look for import from src.core.assistants
                        assistant_imports = re.findall(r'from (src\.assistants(?:\.\w+)*\.\w+Assistant)', content)
                        for a in assistant_imports:
                            uid = a.split(".")[-1]
                            assistant_uri = URIRef(str(ABI.Assistant) + "#" + uid)
                            if (assistant_uri, RDF.type, OWL.NamedIndividual) not in graph:
                                module = importlib.import_module(a)
                                title, slug, description, prompt, avatar, x, y = get_assistant_metadata(uid, module, coordinates)
                                assistant_uri = graph.add_individual_to_prefix(
                                    prefix=ABI,
                                    uid=uid,
                                    label=title,
                                    is_a=ABI.Assistant,
                                    description=description,
                                    avatar=avatar,
                                    prompt=prompt,
                                    slug=slug,
                                    ontology_group="Assistants",
                                    x=x,
                                    y=y,
                                )
                            else:
                                logger.debug(f"Assistant {a} already exists.")

                            logger.debug(f"Adding relation between assistant {assistant} and assistant {assistant_uri}")
                            graph.add((assistant, ABI.communicatesWithAssistant, assistant_uri))
                except ImportError as e:
                    logger.error(f"Error importing assistant {file.stem}: {e}")

    def scan_pipelines(self, graph: Graph) -> None:
        """Scan pipelines directory and add to graph."""
        pipelines_dir = Path("src/pipelines/github")
        nb_pipelines = len(list(pipelines_dir.glob("*.py")))
        logger.debug(f"---> Found {nb_pipelines} pipelines.")
        coordinates = self.__generate_coordinates(700, nb_pipelines, 45)
        i = 0
        for file in pipelines_dir.glob("*.py"):
            if "__PipelineTemplate__" in str(file):
                continue
            if file.stem == "GithubIssuePipeline":
                try:
                    x = coordinates[i][0]
                    y = coordinates[i][1]

                    module = importlib.import_module(f"src.data.pipelines.github.{file.stem}")
                    doc = inspect.getdoc(module)

                    pipeline = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=str(file.stem),
                        label=file.stem.replace("Pipeline", " ") + "Pipeline",
                        is_a=ABI.Pipeline,
                        description=doc,
                        ontology_group="Pipelines",
                        x=x,
                        y=y,
                    )
                    i += 1
                    # Add integrations relations
                    github_integration = URIRef(str(ABI.Integration) + "#GithubIntegration")
                    github_graphql_integration = URIRef(str(ABI.Integration) + "#GithubGraphqlIntegration")
                    graph.add((pipeline, ABI.integratesWith, github_integration))
                    graph.add((pipeline, ABI.integratesWith, github_graphql_integration))

                    # Add ontologies
                    task_ontology = URIRef(str(ABI.Ontology) + "#TaskOntology")
                    platform_ontology = URIRef(str(ABI.Ontology) + "#PlatformOntology")
                    graph.add((pipeline, ABI.usesOntology, task_ontology))
                    graph.add((pipeline, ABI.usesOntology, platform_ontology))

                    # Add assistants relations
                    operations_assistant = URIRef(str(ABI.Assistant) + "#OperationsAssistant")
                    graph.add((operations_assistant, ABI.processesPipeline, pipeline))
                except Exception as e:
                    logger.error(f"Error processing pipeline {file}: {e}")

    def scan_workflows(self, graph: Graph) -> None:
        """Scan workflows directory and add to graph."""
        workflows_dir = Path("src/workflows/operations_assistant")
        nb_workflows = len(list(workflows_dir.glob("*.py")))
        logger.debug(f"---> Found {nb_workflows} workflows.")
        coordinates = self.__generate_coordinates(350, nb_workflows, 25)
        i = 0
        for file in workflows_dir.glob("*.py"):
            if "__WorkflowTemplate__" in str(file):
                continue
            if file.stem == "GetTopPrioritiesWorkflow":
                try:
                    x = coordinates[i][0]
                    y = coordinates[i][1]

                    module = importlib.import_module(f"src.core.workflows.operations.{file.stem}")
                    doc = inspect.getdoc(module)

                    workflow = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=str(file.stem),
                        label=file.stem.replace("Workflow", " "),
                        is_a=ABI.Workflow,
                        description=doc,
                        ontology_group="Workflows",
                        x=x,
                        y=y,
                    )
                    i += 1
                    # Add ontologies relations
                    task_ontology = URIRef(str(ABI.Ontology) + "#TaskOntology")
                    graph.add((workflow, ABI.usesOntology, task_ontology))

                    # Add assistants relations
                    operations_assistant = URIRef(str(ABI.Assistant) + "#OperationsAssistant")
                    graph.add((operations_assistant, ABI.executesWorkflow, workflow))
                except Exception as e:
                    logger.error(f"Error processing workflow {file}: {e}")


    def run(self, parameters: OntologyPipelineParameters) -> Graph:
        """Executes the pipeline to create the ABI ontology.
        
        Args:
            parameters (ABIOntologyParameters): Pipeline parameters
            
        Returns:
            Graph: The resulting RDF graph
        """
        graph = ABIGraph()

        # Scan and add components
        logger.debug(f"-----> Scanning integrations")
        self.scan_integrations(graph)
        logger.debug(f"-----> Scanning ontologies")
        self.scan_ontologies(graph)
        logger.debug(f"-----> Scanning assistants")
        self.scan_assistants(graph)
        logger.debug(f"-----> Scanning pipelines")
        self.scan_pipelines(graph)
        logger.debug(f"-----> Scanning workflows")
        self.scan_workflows(graph)

        # Store the graph
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)

        from src.mappings import COLORS_NODES
        # Generate YAML data with mapping colors
        yaml_data = OntologyYaml.rdf_to_yaml(graph, class_colors_mapping=COLORS_NODES, display_relations_names=False)

        # Initialize parameters
        workspace_id = parameters.workspace_id
        onto_label = parameters.label
        onto_description = parameters.description
        onto_logo_url = parameters.logo_url
        onto_level = parameters.level

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
                    level=onto_level,
                    description=onto_description,
                    logo_url=onto_logo_url,
                )
                ontology_id = _.get(res, "ontology.id")
                logger.info(f"✅ Ontology '{ontology_id}' successfully created.")
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
                func=lambda **kwargs: self.run(OntologyPipelineParameters(**kwargs)),
                args_schema=OntologyPipelineParameters
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
        def run(parameters: OntologyPipelineParameters):
            return self.run(parameters).serialize(format="turtle") 

if __name__ == "__main__":
    from src import secret, config
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    from abi.services.ontology_store.OntologyStoreService import OntologyStoreService

    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))

    pipeline = AbiApplicationPipeline(AbiApplicationPipelineConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=secret.get("NAAS_API_KEY")
        ),
        ontology_store=ontology_store
    ))
    pipeline.run(OntologyPipelineParameters())
