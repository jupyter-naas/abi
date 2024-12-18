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
                    
                    subfolder = str(file.parent.name).lower()
                    ranking_mapping = {
                        "foundation": 1,
                        "domain": 2,
                        "expert": 3
                    }
                    ranking = ranking_mapping.get(subfolder, 4)  # Default to 4 if not found
                    
                    module = importlib.import_module(import_path)
                    title = (file.stem.replace("Assistant", " ")) + "Assistant"
                    slug = title.lower().replace(" ", "-").replace("_", "-")
                    results.append({
                        "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                        "type": "assistant", 
                        "category": subfolder,
                        "title": getattr(module, "NAME", title),
                        "description": getattr(module, "DESCRIPTION", ""),
                        "image_url": getattr(module, "AVATAR_URL", ""),
                        "source_url": f"https://github.com/abi/src/assistants/{relative_path}",
                        "ranking": ranking,
                        "slug": getattr(module, "SLUG", slug),
                        "model": getattr(module, "MODEL", "gpt-4o-mini"), 
                        "temperature": getattr(module, "TEMPERATURE", 0),
                        "system_prompt": getattr(module, "SYSTEM_PROMPT", ""),
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
                            "source_url": f"https://github.com/abi/src/workflows/{relative_path}",
                            "ranking": 1
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
                            "source_url": f"https://github.com/abi/src/data/pipelines/{relative_path}",
                            "ranking": 1
                        })
                except ImportError as e:
                    logger.error(f"Error importing pipeline {file.stem}: {e}")
        
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
                        results.append({
                            "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                            "type": "integration",
                            "title": (file.stem.replace("Integration", " ")) + "Integration",
                            "category": "tool",
                            "description": doc,
                            "image_url": logo_url,
                            "source_url": f"https://github.com/abi/src/integrations/{file.name}",
                            "ranking": 1
                        })
                except ImportError as e:
                    logger.error(f"Error importing integration {file.stem}: {e}")
        
        return results

    def __scan_ontologies(self) -> List[Dict[str, str]]:
        """Scan ontologies directory and collect metadata."""
        results = []
        ontologies_dir = Path("src/ontologies")
        
        for file in ontologies_dir.rglob("*.ttl"):
            if "__OntologyTemplate__" in str(file) or "ConsolidatedOntology" in str(file):
                continue
            logger.info(f"Processing ontology {file}")
            try:
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
                    ranking = 1
                elif is_mid_level:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_CCO.png"
                    ranking = 2
                elif is_domain:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
                    ranking = 3
                elif is_application:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
                    ranking = 4
                else:
                    image_url = ""
                    ranking = 5
                # Add ontology entry
                title = next(g.objects(None, DC.title), next(g.objects(None, OWL.Ontology), next(g.objects(None, RDFS.label), "")))
                logger.info(f"Ontology Title: {title}")
                results.append({
                    "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                    "type": "ontology",
                    "category": "ontology",
                    "title": title,
                    "description": next(g.objects(None, DC.description), ""),
                    "image_url": image_url,
                    "source_url": next(g.objects(None, OWL.versionIRI), f"https://github.com/abi/src/ontologies/{file.name}"),
                    "ranking": ranking,
                    "comment": next(g.objects(None, RDFS.comment), ""),
                    "contributors": ", ".join(g.objects(None, DC11.contributor)),
                    "licence": next(g.objects(None, DC.license), next(g.objects(None, DCTERMS.license), "")),
                })
                
                # Add classes
                for s in g.subjects(RDFS.subClassOf, None):
                    if isinstance(s, URIRef):
                        # Get subClassOf and its label
                        subclass_of = next(g.objects(s, RDFS.subClassOf), "")
                        subclass_of_label = ""
                        if subclass_of:
                            subclass_of_label = next(g.objects(subclass_of, RDFS.label), str(subclass_of).split("/")[-1])

                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontology",
                            "category": "class",
                            "title": next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ''),
                            "image_url": "",
                            "source_url": str(s),
                            "ranking": ranking,
                            "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}"),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "example": next(g.objects(s, SKOS.example), ''),
                            "subClassOf": subclass_of,
                            "subClassOfLabel": subclass_of_label.capitalize() if subclass_of_label else ""
                        })

                # Add object properties
                for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty)):
                    if isinstance(s, URIRef):
                        # Get domain
                        domain_objs = list(g.objects(s, RDFS.domain))
                        domain_labels = [next(g.objects(domain_obj, RDFS.label), "") for domain_obj in domain_objs if domain_obj and str(domain_obj).startswith("http")]
                        domain = [str(domain_obj) for domain_obj in domain_objs if domain_obj and str(domain_obj).startswith("http")]
                        domain_info = {
                            "domains": domain,
                            "labels": domain_labels,
                            "type": "union" if len(domain) > 1 else "single"
                        }
                        
                        # Get range
                        range_objs = list(g.objects(s, RDFS.range))
                        range_labels = [next(g.objects(range_obj, RDFS.label), "") for range_obj in range_objs if range_obj and str(range_obj).startswith("http")]
                        range_val = [str(range_obj) for range_obj in range_objs if range_obj and str(range_obj).startswith("http")]
                        range_info = {
                            "ranges": range_val,
                            "labels": range_labels,
                            "type": "union" if len(range_val) > 1 else "single"
                        }
                        
                        # Get subPropertyOf
                        sub_prop = next(g.objects(s, RDFS.subPropertyOf), "")
                        sub_prop_val = str(sub_prop).split("/")[-1] if sub_prop else ""
                        
                        # Get subPropertyOf label if it exists
                        sub_prop_label = ""
                        if sub_prop:
                            sub_prop_label = next(g.objects(sub_prop, RDFS.label), sub_prop_val)
                        
                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontology",
                            "category": "object_property",
                            "title": next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ''),
                            "image_url": "",
                            "source_url": str(s),
                            "ranking": ranking,
                            "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}"),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "example": next(g.objects(s, SKOS.example), ''),
                            "domain": domain_info,
                            "range": range_info,
                            "subPropertyOf": sub_prop_val,
                            "subPropertyOfLabel": sub_prop_label.capitalize() if sub_prop_label else ""
                        })
                        
                # Add data properties
                for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty)):
                    if isinstance(s, URIRef):
                        # Get range 
                        range_obj = next(g.objects(s, RDFS.range), "")
                        range_val = str(range_obj).split("#")[-1] if range_obj else ""
                        range_label = next(g.objects(range_obj, RDFS.label), "") if range_obj else ""

                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontology",
                            "category": "data_property",
                            "title": next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ""),
                            "image_url": "",
                            "source_url": str(s),
                            "ranking": ranking,
                            "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}"),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "example": next(g.objects(s, SKOS.example), ""),
                            "range": range_val,
                            "range_label": range_label,
                        })

                # Add annotation properties
                for s, p, o in g.triples((None, RDF.type, OWL.AnnotationProperty)):
                    if isinstance(s, URIRef):
                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontology",
                            "category": "annotation_property",
                            "title": next(g.objects(s, RDFS.label), str(s).split("/")[-1].split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ""),
                            "image_url": "",
                            "source_url": str(s),
                            "ranking": ranking,
                            "ontology_source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}"),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "example": next(g.objects(s, SKOS.example), ""),
                        })
                
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

        workflows = self.__scan_workflows()
        logger.info(f"Found {len(workflows)} workflows")
        all_records.extend(workflows)

        pipelines = self.__scan_pipelines()
        logger.info(f"Found {len(pipelines)} pipelines")
        all_records.extend(pipelines)

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