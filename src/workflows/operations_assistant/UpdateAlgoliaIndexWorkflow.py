from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.AlgoliaIntegration import AlgoliaIntegration, AlgoliaIntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict, Any
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import re
import importlib
import inspect
from rdflib import Graph, URIRef, RDFS, OWL, SKOS, RDF
from rdflib.namespace import Namespace
from pathlib import Path
import hashlib
import asyncio

CCO = Namespace("https://www.commoncoreontologies.org/")
DC = DCTERMS = Namespace("http://purl.org/dc/terms/")
DC11 = Namespace("http://purl.org/dc/elements/1.1/")

@dataclass
class UpdateAlgoliaIndexConfiguration(WorkflowConfiguration):
    """Configuration for UpdateAlgoliaIndex workflow.
    
    Attributes:
        algolia_integration_config (AlgoliaIntegrationConfiguration): Configuration for Algolia integration
    """
    algolia_integration_config: AlgoliaIntegrationConfiguration

class UpdateAlgoliaIndexParameters(WorkflowParameters):
    """Parameters for UpdateAlgoliaIndex execution."""
    index_name: str = Field(default="abi-search", description="Name of the Algolia index to update")

class UpdateAlgoliaIndexWorkflow(Workflow):
    __configuration: UpdateAlgoliaIndexConfiguration
    
    def __init__(self, configuration: UpdateAlgoliaIndexConfiguration):
        self.__configuration = configuration
        self.__algolia = AlgoliaIntegration(self.__configuration.algolia_integration_config)

    def __scan_assistants(self) -> List[Dict[str, str]]:
        """Scan assistants directory and collect metadata."""
        results = []
        assistants_dir = Path("src/assistants")
        
        for file in assistants_dir.rglob("*.py"):
            if "__AssistantTemplate__" in str(file):
                continue
            if file.stem.endswith("Assistant"):
                logger.info(f"Processing assistant {file}")
                try:
                    # Build import path based on file location
                    import_path = "src.assistants"
                    relative_path = file.relative_to(assistants_dir)
                    if len(relative_path.parts) > 1:
                        # File is in subfolder(s)
                        import_path += "." + ".".join(relative_path.parts[:-1])
                    import_path += f".{file.stem}"
                    
                    subfolder = str(relative_path.parts[0]).lower()
                    ranking_mapping = {
                        "foundation": 1,
                        "domain": 2,
                        "expert": 3
                    }
                    ranking = ranking_mapping.get(subfolder, 4)  # Default to 4 if not found
                    
                    module = importlib.import_module(import_path)
                    title = (file.stem.replace("Assistant", " ")) + "Assistant"
                    slug = title.lower().replace(" ", "-").replace("_", "-")
                    
                    # # Get available tools
                    # tools = []
                    # # Find create_*_agent function dynamically
                    # create_agent_funcs = [f for f in dir(module) if f.startswith("create_") and f.endswith("_agent")]
                    # for create_func in create_agent_funcs:
                    #     try:
                    #         agent = getattr(module, create_func)()
                    #         if hasattr(agent, "tools"):
                    #             tools = [
                    #                 {
                    #                     "name": tool.name,
                    #                     "description": tool.description
                    #                 }
                    #                 for tool in agent.tools
                    #             ]
                    #             break  # Use first successful agent creation
                    #     except Exception as e:
                    #         logger.warning(f"Could not get tools for {file.stem} using {create_func}: {e}")
                    
                    results.append({
                        "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                        "type": "assistant", 
                        "category": subfolder,
                        "title": getattr(module, "NAME", title),
                        "description": getattr(module, "DESCRIPTION", ""),
                        "image_url": getattr(module, "AVATAR_URL", ""),
                        "source_title": subfolder.capitalize(),
                        "source_url": f"https://github.com/jupyter-naas/abi/src/assistants/{relative_path}",
                        "ranking": ranking,
                        "slug": getattr(module, "SLUG", slug),
                        "model": getattr(module, "MODEL", "gpt-4o-mini"), 
                        "temperature": getattr(module, "TEMPERATURE", 0),
                        "system_prompt": getattr(module, "SYSTEM_PROMPT", ""),
                        # "tools": "\n".join([f"- {tool['name']}: {tool['description']}" for tool in tools])  # Add tools with descriptions
                    })
                except ImportError as e:
                    logger.error(f"Error importing assistant {file.stem}: {e}")
        
        return results

    def __scan_workflows(self) -> List[Dict[str, str]]:
        """Scan workflows directory and collect metadata."""
        results = []
        workflows_dir = Path("src/workflows")
        
        for file in workflows_dir.rglob("*.py"):
            if "__WorkflowTemplate__" in str(file):
                continue
            if file.stem.endswith("Workflow"):
                logger.info(f"Processing workflow {file}")
                try:
                    # Build import path based on file location
                    import_path = "src.workflows"
                    relative_path = file.relative_to(workflows_dir)
                    if len(relative_path.parts) > 1:
                        # File is in subfolder(s)
                        import_path += "." + ".".join(relative_path.parts[:-1])
                    import_path += f".{file.stem}"
                    
                    module = importlib.import_module(import_path)
                    class_name = file.stem
                    if hasattr(module, class_name):
                        workflow_class = getattr(module, class_name)
                        doc = inspect.getdoc(workflow_class) or ""
                        results.append({
                            "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                            "type": "workflow",
                            "category": file.parent.name,
                            "title": " ".join(re.findall('[A-Z][^A-Z]*', file.stem.replace("Workflow", ""))).strip() + " Workflow",
                            "description": doc,
                            "image_url": "",
                            "source_title": (file.parent.name).replace("_", " ").capitalize(),
                            "source_url": f"https://github.com/jupyter-naas/abi/src/workflows/{relative_path}",
                            "ranking": 2
                        })
                except ImportError as e:
                    logger.error(f"Error importing workflow {file.stem}: {e}")
        
        return results
    
    def __scan_pipelines(self) -> List[Dict[str, str]]:
        """Scan pipelines directory and collect metadata."""
        results = []
        pipelines_dir = Path("src/data/pipelines")
        
        for file in pipelines_dir.rglob("*.py"):
            if "__PipelineTemplate__" in str(file):
                continue
            if file.stem.endswith("Pipeline"):
                logger.info(f"Processing pipeline {file}")
                try:
                    # Build import path based on file location
                    import_path = "src.data.pipelines"
                    relative_path = file.relative_to(pipelines_dir)
                    if len(relative_path.parts) > 1:
                        # File is in subfolder(s)
                        import_path += "." + ".".join(relative_path.parts[:-1])
                    import_path += f".{file.stem}"
                    
                    module = importlib.import_module(import_path)
                    class_name = file.stem
                    if hasattr(module, class_name):
                        pipeline_class = getattr(module, class_name)
                        doc = inspect.getdoc(pipeline_class) or ""
                        results.append({
                            "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                            "type": "data",
                            "category": "pipeline",
                            "title": " ".join(re.findall('[A-Z][^A-Z]*', file.stem.replace("Pipeline", ""))).strip() + " Pipeline",
                            "description": doc,
                            "image_url": "",
                            "source_title": relative_path.parts[0] if len(relative_path.parts) > 1 else file.stem.replace("Pipeline", ""),
                            "source_url": f"https://github.com/jupyter-naas/abi/src/data/pipelines/{relative_path}",
                            "ranking": 2
                        })
                except ImportError as e:
                    logger.error(f"Error importing pipeline {file.stem}: {e}")
        
        return results

    def __scan_models(self) -> List[Dict[str, str]]:
        """Scan models directory and collect metadata."""
        results = []
        models_dir = Path("src/models/naas")
        
        for file in models_dir.glob("*.py"):
            if "__ModelTemplate__" in str(file):
                continue
            if file.stem.endswith("AIModel"):
                logger.info(f"Processing model {file}")
                try:
                    module = importlib.import_module(f"src.models.naas.{file.stem}")
                    
                    # Get model attributes
                    model_id = getattr(module, "ID", "")
                    name = getattr(module, "NAME", "")
                    description = getattr(module, "DESCRIPTION", "")
                    image = getattr(module, "IMAGE", "")
                    model_type = getattr(module, "MODEL_TYPE", "")
                    context_window = getattr(module, "CONTEXT_WINDOW", 0)
                    owner = getattr(module, "OWNER", "")
                    
                    results.append({
                        "objectID": model_id,
                        "type": "model",
                        "category": model_type,
                        "title": name,
                        "description": description,
                        "image_url": image,
                        "source_title": owner.capitalize(),
                        "source_url": f"https://github.com/jupyter-naas/abi/src/models/naas/{file.name}",
                        "ranking": 2,
                        "context_window": context_window
                    })
                except ImportError as e:
                    logger.error(f"Error importing model {file.stem}: {e}")
        
        return results

    def __scan_integrations(self) -> List[Dict[str, str]]:
        """Scan integrations directory and collect metadata."""
        results = []
        integrations_dir = Path("src/integrations")
        
        for file in integrations_dir.glob("*.py"):
            if "__IntegrationTemplate__" in str(file):
                continue
            if file.stem.endswith("Integration"):
                logger.info(f"Processing integration {file}")
                try:
                    module = importlib.import_module(f"src.integrations.{file.stem}")
                    class_name = file.stem
                    if hasattr(module, class_name):
                        integration_class = getattr(module, class_name)
                        doc = inspect.getdoc(integration_class) or ""
                        logo_url = getattr(module, "LOGO_URL", "")
                        source_title = file.stem.replace("Integration", "")

                        # Add main integration record
                        integration_id = hashlib.sha256(file.stem.encode()).hexdigest()
                        results.append({
                            "objectID": integration_id,
                            "type": "integration",
                            "title": (file.stem.replace("Integration", " ")) + "Integration",
                            "category": "tool",
                            "description": doc,
                            "image_url": logo_url,
                            "source_title": source_title,
                            "source_url": f"https://github.com/jupyter-naas/abi/src/integrations/{file.name}",
                            "ranking": 1,
                            # "args_schema": "\n".join([
                            #     f"{field.name}: {field.metadata.get('description', '')}"
                            #     for field in (config_class.__dataclass_fields__.values() if config_class and hasattr(config_class, '__dataclass_fields__') else [])
                            # ]) if config_class and hasattr(config_class, '__dataclass_fields__') else ""
                        })
                        
                        # Get tools if as_tools function exists
                        if hasattr(module, "as_tools"):
                            try:
                                # Create dummy configuration to get tools
                                config_class = getattr(module, f"{file.stem}Configuration")
                                dummy_config = config_class(**{
                                    field.name: "dummy" if field.type == str else 0
                                    for field in config_class.__dataclass_fields__.values()
                                })
                                
                                tool_list = module.as_tools(dummy_config)
                                for tool in tool_list:
                                    # Create a unique ID for each function
                                    function_id = hashlib.sha256(f"{file.stem}_{tool.name}".encode()).hexdigest()
                                    
                                    # Add function record
                                    results.append({
                                        "objectID": function_id,
                                        "type": "integration",
                                        "title": (tool.name).replace("_", " ").capitalize(),
                                        "category": "function",
                                        "description": tool.description,
                                        "image_url": logo_url,
                                        "source_title": source_title,
                                        "source_url": f"https://github.com/jupyter-naas/abi/src/integrations/{file.name}",
                                        "ranking": 2,
                                        "args_schema": "\n".join([
                                            f"-{name}: {field.description}\n"
                                            for name, field in (tool.args_schema.__fields__.items() if hasattr(tool, 'args_schema') else [])
                                        ]) if hasattr(tool, 'args_schema') else str(tool.args if hasattr(tool, 'args') else {})
                                    })
                            except Exception as e:
                                logger.warning(f"Could not get tools for {file.stem}: {e}")
                except ImportError as e:
                    logger.error(f"Error importing integration {file.stem}: {e}")
        
        return results
    
    def __scan_analytics(self) -> List[Dict[str, str]]:
        """Scan analytics directory and collect metadata."""
        results = []
        analytics_dir = Path("src/analytics")
        
        # Recursively scan all .py files in analytics directory and subdirectories
        for file in analytics_dir.rglob("*.py"):
            # Skip template files
            if "__AnalyticTemplate__" in str(file):
                continue
                
            # Only process files ending with Analytics
            if file.stem.endswith("Analytics"):
                logger.info(f"Processing analytic {file}")
                try:
                    # Build import path based on file location
                    import_path = "src.analytics"
                    relative_path = file.relative_to(analytics_dir)
                    
                    # Add subdirectories to import path if file is nested
                    if len(relative_path.parts) > 1:
                        import_path += "." + ".".join(relative_path.parts[:-1])
                    import_path += f".{file.stem}"
                    module = importlib.import_module(import_path)
                    
                    # Get analytic class
                    class_name = file.stem
                    if hasattr(module, class_name):
                        analytic_class = getattr(module, class_name)
                        doc = inspect.getdoc(analytic_class) or ""
                        logo_url = getattr(module, "LOGO_URL", "")
                        source_title = file.stem.replace("Analytics", "")

                        # Add main analytic record
                        analytic_id = hashlib.sha256(file.stem.encode()).hexdigest()
                        results.append({
                            "objectID": analytic_id,
                            "type": "analytic",
                            "title": (file.stem.replace("Analytics", " ")),
                            "category": "tool",
                            "description": doc,
                            "image_url": logo_url,
                            "source_title": source_title,
                            "source_url": f"https://github.com/jupyter-naas/abi/src/analytics/{relative_path}",
                            "ranking": 1
                        })
                        
                        # Get tools if as_tools function exists
                        if hasattr(module, "as_tools"):
                            try:
                                # Create dummy configuration to get tools
                                config_class = getattr(module, f"{file.stem}Configuration")
                                dummy_config = config_class(**{
                                    field.name: "dummy" if field.type == str else 0
                                    for field in config_class.__dataclass_fields__.values()
                                })
                                
                                tool_list = module.as_tools(dummy_config)
                                for tool in tool_list:
                                    # Create unique ID for each function
                                    function_id = hashlib.sha256(f"{file.stem}_{tool.name}".encode()).hexdigest()
                                    
                                    # Add function record
                                    results.append({
                                        "objectID": function_id,
                                        "type": "analytic",
                                        "title": (tool.name).replace("_", " ").capitalize(),
                                        "category": "function",
                                        "description": tool.description,
                                        "image_url": logo_url,
                                        "source_title": source_title,
                                        "source_url": f"https://github.com/jupyter-naas/abi/src/analytics/{relative_path}",
                                        "ranking": 2,
                                        "args_schema": "\n".join([
                                            f"-{name}: {field.description}\n"
                                            for name, field in (tool.args_schema.__fields__.items() if hasattr(tool, 'args_schema') else [])
                                        ]) if hasattr(tool, 'args_schema') else str(tool.args if hasattr(tool, 'args') else {})
                                    })
                            except Exception as e:
                                logger.warning(f"Could not get tools for {file.stem}: {e}")
                except ImportError as e:
                    logger.error(f"Error importing analytic {file.stem}: {e}")
        
        return results

    def __scan_ontologies(self) -> List[Dict[str, str]]:
        """Scan ontologies directory and collect metadata."""
        results = []
        ontologies_dir = Path("src/ontologies")

        # Create dictionary mapping URIs to their RDFS labels
        uri_to_label = {}
        for file in ontologies_dir.rglob("*.ttl"):
            if "__OntologyTemplate__" not in str(file) and "ConsolidatedOntology" not in str(file):
                try:
                    g = Graph()
                    g.parse(file, format="turtle")
                    
                    # Get all subjects with RDFS labels
                    for s, p, o in g.triples((None, RDFS.label, None)):
                        if isinstance(s, URIRef):  # Only include URIRef subjects
                            uri_to_label[str(s)] = str(o)
                except Exception as e:
                    logger.error(f"Error processing {file} for labels: {e}")
        
        logger.info(f"Found {len(uri_to_label)} labels")
        
        for file in ontologies_dir.rglob("*.ttl"):
            if "__OntologyTemplate__" in str(file) or "ConsolidatedOntology" in str(file):
                continue
            logger.info(f"Processing ontology {file}")
            try:
                g = Graph()
                g.parse(file, format="turtle")

                # Get ontology title
                ontology_title = next(g.objects(None, DC.title), next(g.objects(None, OWL.Ontology), next(g.objects(None, RDFS.label), "")))

                # Get ontology type from file path
                is_top_level = "top-level" in str(file)
                is_mid_level = "mid-level" in str(file)
                is_domain = "domain-level" in str(file)
                is_application = "application-level" in str(file)
                
                # Set image URL based on ontology type
                if is_top_level:
                    image_url = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/2b9ac8af-4026-4173-8796-1c2de5d34966/images/2dd774ba51a94b4eb4d29d444e7771cc"
                    ranking = 1
                    source_title = "BFO"
                elif is_mid_level:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_CCO.png"
                    ranking = 2
                    source_title = "CCO"
                elif is_domain:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
                    ranking = 3
                    source_title = "Domain Ontology"
                elif is_application:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
                    ranking = 4
                    source_title = "Application Ontology"
                else:
                    image_url = ""
                    ranking = 5
                    source_title = "Unknown"
                    
                # Add ontology entry
                results.append({
                    "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                    "type": "ontology",
                    "category": "ontology",
                    "title": ontology_title,
                    "description": next(g.objects(None, DC.description), "No description provided."),
                    "image_url": image_url,
                    "source_title": source_title,
                    "source_url": next(g.objects(None, OWL.versionIRI), f"https://github.com/jupyter-naas/abi/src/ontologies/{file.name}"),
                    "ranking": ranking,
                    "comment": next(g.objects(None, RDFS.comment), ""),
                    "contributors": ", ".join(g.objects(None, DC11.contributor)),
                    "licence": next(g.objects(None, DC.license), next(g.objects(None, DCTERMS.license), "")),
                })
                
                # Add classes
                try:
                    classes = []
                    for s in g.subjects(RDFS.subClassOf, None):
                        if isinstance(s, URIRef):
                            # Get subClassOf and its label
                            subclass_of = next(g.objects(s, RDFS.subClassOf), "")
                            subclass_of_label = ""
                            if subclass_of:
                                # subclass_of_label = next(g.objects(subclass_of, RDFS.label).capitalize(), str(subclass_of).split("/")[-1])
                                subclass_of_label = uri_to_label.get(str(subclass_of), "").capitalize()

                            classes.append({
                                "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                                "type": "ontology",
                                "category": "class",
                                "title": "Class: " + next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                                "description": next(g.objects(s, SKOS.definition), "No definition provided."),
                                "image_url": image_url,
                                "source_title": ontology_title,
                                "source_url": str(s),
                                "ranking": ranking+1,
                                "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/jupyter-naas/abi/src/ontologies/{file.name}"),
                                "comment": next(g.objects(s, RDFS.comment), ""),
                                "example": next(g.objects(s, SKOS.example), ''),
                                "subClassOf": subclass_of,
                                "subClassOfLabel": subclass_of_label
                            })

                    logger.info(f"Found {len(classes)} classes")
                    results.extend(classes)
                except Exception as e:
                    logger.error(f"Error processing classes {file}: {e}")

                # Add object properties
                object_properties = []
                try:
                    for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty)):
                        if isinstance(s, URIRef):
                            # Get domain and range
                            domain_objs = [str(obj) for obj in g.objects(s, RDFS.domain) if str(obj).startswith('http')]
                            range_objs = [str(obj) for obj in g.objects(s, RDFS.range) if str(obj).startswith('http')]
                            
                        # # Map domain objects to classes
                        # domain_classes = []
                        # for domain_obj in domain_objs:
                        #     if isinstance(domain_obj, URIRef):
                        #         # Check if domain is a union
                        #         union_list = list(g.objects(domain_obj, OWL.unionOf))
                        #         if union_list:
                        #             # Handle union case
                        #             union_classes = []
                        #             # Get the list of classes in the union
                        #             for item in g.items(union_list[0]):
                        #                 if isinstance(item, URIRef):
                        #                     union_classes.append(str(item))
                        #             domain_classes.append({
                        #                 "from": union_classes,
                        #                 "type": "union"
                        #             })
                        #         else:
                        #             # Handle single class case
                        #             domain_classes.append({
                        #                 "from": [str(domain_obj)],
                        #                 "type": "single"
                        #             })
                                    
                        # # Map range objects to classes
                        # range_classes = []
                        # for range_obj in range_objs:
                        #     if isinstance(range_obj, URIRef):
                        #         # Check if range is a union
                        #         union_list = list(g.objects(range_obj, OWL.unionOf))
                        #         if union_list:
                        #             # Handle union case
                        #             union_classes = []
                        #             # Get the list of classes in the union
                        #             for item in g.items(union_list[0]):
                        #                 if isinstance(item, URIRef):
                        #                     union_classes.append(str(item))
                        #             range_classes.append({
                        #                 "to": union_classes,
                        #                 "type": "union"
                        #             })
                        #         else:
                        #             # Handle single class case
                        #             range_classes.append({
                        #                 "to": [str(range_obj)],
                        #                 "type": "single"
                        #             })
                            
                            # Get subPropertyOf
                            sub_prop = next(g.objects(s, RDFS.subPropertyOf), "")
                            sub_prop_val = str(sub_prop).split("/")[-1] if sub_prop else ""
                            
                            # Get subPropertyOf label if it exists
                            sub_prop_label = ""
                            if sub_prop:
                                # sub_prop_label = next(g.objects(sub_prop, RDFS.label), sub_prop_val)
                                sub_prop_label = uri_to_label.get(str(sub_prop), "").capitalize()

                            object_properties.append({
                                "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                                "type": "ontology",
                                "category": "object_property",
                                "title": "Object Property: " + next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]),
                                "description": next(g.objects(s, SKOS.definition), "No definition provided."),
                                "image_url": image_url,
                                "source_title": ontology_title,
                                "source_url": str(s),
                                "ranking": ranking+1,
                                "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/jupyter-naas/abi/src/ontologies/{file.name}"),
                                "comment": next(g.objects(s, RDFS.comment), ""),
                                "example": next(g.objects(s, SKOS.example), ''),
                                "domain": domain_objs,
                                "range": range_objs,
                                "subPropertyOf": sub_prop_val,
                                "subPropertyOfLabel": sub_prop_label
                            })

                    logger.info(f"Found {len(object_properties)} object properties")
                    results.extend(object_properties)
                except Exception as e:
                    logger.error(f"Error processing object properties {file}: {e}") 
                            
                # Add data properties
                data_properties = []
                try:
                    for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty)):
                        if isinstance(s, URIRef):
                            # Get range 
                            range_obj = next(g.objects(s, RDFS.range), "")
                            range_val = str(range_obj).split("#")[-1] if range_obj else ""
                            range_label = next(g.objects(range_obj, RDFS.label), "") if range_obj else ""

                            data_properties.append({
                                "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                                "type": "ontology",
                                "category": "data_property",
                                "title": "Data Property: " + next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                                "description": next(g.objects(s, SKOS.definition), "No definition provided."),
                                "image_url": image_url,
                                "source_title": ontology_title,
                                "source_url": str(s),
                                "ranking": ranking+1,
                                "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/jupyter-naas/abi/src/ontologies/{file.name}"),
                                "comment": next(g.objects(s, RDFS.comment), ""),
                                "example": next(g.objects(s, SKOS.example), ""),
                                "range": range_val,
                                "range_label": range_label,
                            })
                    logger.info(f"Found {len(data_properties)} data properties")
                    results.extend(data_properties)
                except Exception as e:
                    logger.error(f"Error processing data properties {file}: {e}")

                # Add annotation properties
                annotation_properties = []
                try:
                    for s, p, o in g.triples((None, RDF.type, OWL.AnnotationProperty)):
                        if isinstance(s, URIRef):
                            annotation_properties.append({
                                "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                                "type": "ontology",
                                "category": "annotation_property",
                                "title": "Annotation Property: " + next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                                "description": next(g.objects(s, SKOS.definition), "No definition provided."),
                                "image_url": image_url,
                                "source_title": ontology_title,
                                "source_url": str(s),
                                "ranking": ranking+1,
                                "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/jupyter-naas/abi/src/ontologies/{file.name}"),
                                "comment": next(g.objects(s, RDFS.comment), ""),
                                "example": next(g.objects(s, SKOS.example), ""),
                            })

                    logger.info(f"Found {len(annotation_properties)} annotation properties")
                    results.extend(annotation_properties)
                except Exception as e:
                    logger.error(f"Error processing annotation properties {file}: {e}")

            except Exception as e:
                logger.error(f"Error processing ontology {file}: {e}")
        
        return results

    async def run(self, parameters: UpdateAlgoliaIndexParameters) -> Dict[str, Any]:
        """Updates the Algolia index with all collected data.
        
        Returns:
            Dict[str, Any]: Summary of the update operation
        """
        all_records = []
        
        # Collect all data
        assistants = self.__scan_assistants()
        logger.info(f"Found {len(assistants)} assistants")
        all_records.extend(assistants)

        integrations = self.__scan_integrations()
        logger.info(f"Found {len(integrations)} integrations")
        all_records.extend(integrations)

        analytics = self.__scan_analytics()
        logger.info(f"Found {len(analytics)} analytics")
        all_records.extend(analytics)

        workflows = self.__scan_workflows()
        logger.info(f"Found {len(workflows)} workflows")
        all_records.extend(workflows)

        pipelines = self.__scan_pipelines()
        logger.info(f"Found {len(pipelines)} pipelines")
        all_records.extend(pipelines)

        models = self.__scan_models()
        logger.info(f"Found {len(models)} models")
        all_records.extend(models)

        ontologies = self.__scan_ontologies()
        logger.info(f"Found {len(ontologies)} ontologies")
        all_records.extend(ontologies)
        
        # Save records to local file for backup
        import json
        import os
        from datetime import datetime

        # Create backup directory if it doesn't exist
        backup_dir = "src/data/algolia_backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"algolia_records_{timestamp}.json")

        # Save records to JSON file
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(all_records, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(all_records)} records to {backup_file}")

        # Update Algolia index
        result = await self.__algolia.update_index(parameters.index_name, all_records)
        logger.info(f"Algolia response: {result}")
        return {
            "status": "success",
            "records_processed": len(all_records),
            "algolia_response": len(result)
        }

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [StructuredTool(
            name="update_algolia_index",
            description="Updates the Algolia search index with all assistants, integrations, and ontologies metadata",
            func=lambda **kwargs: asyncio.run(self.run(UpdateAlgoliaIndexParameters(**kwargs))),
            args_schema=UpdateAlgoliaIndexParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/update_algolia_index")
        def update_algolia_index(parameters: UpdateAlgoliaIndexParameters):
            return self.run(parameters) 