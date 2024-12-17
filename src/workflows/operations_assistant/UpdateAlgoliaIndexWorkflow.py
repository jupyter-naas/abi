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

CCO = Namespace("https://www.commoncoreontologies.org/")
DC = Namespace("http://purl.org/dc/terms/")
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
            logger.info(f"Processing assistant {file}")
            if file.stem.endswith("Assistant"):
                try:
                    module = importlib.import_module(f"src.assistants.{file.parent.name}.{file.stem}")
                    results.append({
                        "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                        "type": "assistant", 
                        "title": (file.stem.replace("Assistant", " ")).capitalize() + "Assistant",
                        "description": getattr(module, "DESCRIPTION", ""),
                        "image_url": getattr(module, "AVATAR_URL", ""),
                        "source_url": f"https://github.com/abi/src/assistants/{file.parent.name}/{file.name}"
                    })
                except ImportError as e:
                    logger.error(f"Error importing assistant {file.stem}: {e}")
        
        return results

    def __scan_integrations(self) -> List[Dict[str, str]]:
        """Scan integrations directory and collect metadata."""
        results = []
        integrations_dir = Path("src/integrations")
        
        for file in integrations_dir.glob("*.py"):
            if "__IntegrationTemplate__" in str(file):
                continue
            logger.info(f"Processing integration {file}")
            if file.stem.endswith("Integration"):
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
                            "title": (file.stem.replace("Integration", " ")).capitalize() + "Integration",
                            "description": doc,
                            "image_url": logo_url,
                            "source_url": f"https://github.com/abi/src/integrations/{file.name}"
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
                elif is_mid_level:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_CCO.png"
                elif is_domain:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
                elif is_application:
                    image_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
                else:
                    image_url = ""
                
                # Add ontology entry
                results.append({
                    "objectID": hashlib.sha256(file.stem.encode()).hexdigest(),
                    "type": "ontology", 
                    "title": next(g.objects(None, DC.title), " ".join(re.findall('[A-Z][^A-Z]*', file.stem))).capitalize(),
                    "description": next(g.objects(None, DC.description), ""),
                    "comment": next(g.objects(None, RDFS.comment), ""),
                    "image_url": image_url,
                    "source_url": next(g.objects(None, OWL.versionIRI), f"https://github.com/abi/src/ontologies/{file.name}"),
                    "contributors": ", ".join(g.objects(None, DC11.contributor))
                })
                
                # Add classes
                for s in g.subjects(RDFS.subClassOf, None):
                    if isinstance(s, URIRef):
                        # Get subClassOf and its label
                        subclass_of = next(g.objects(s, RDFS.subClassOf), "")
                        subclass_of_label = ""
                        if subclass_of:
                            subclass_of_label = next(g.objects(subclass_of, RDFS.label), str(subclass_of).split("#")[-1])

                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontologies_class",
                            "title": next(g.objects(s, RDFS.label), str(s).split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ''),
                            "example": next(g.objects(s, SKOS.example), ''),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "image_url": "",
                            "source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}"),
                            "subClassOf": subclass_of,
                            "subClassOfLabel": subclass_of_label
                        })

                # Add object properties
                for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty)):
                    if isinstance(s, URIRef):
                        # Get domain
                        domain_obj = next(g.objects(s, RDFS.domain), "")
                        domain = str(domain_obj).split("#")[-1] if domain_obj else ""
                        
                        # Get range
                        range_obj = next(g.objects(s, RDFS.range), "")
                        range_val = str(range_obj).split("#")[-1] if range_obj else ""
                        
                        # Get subPropertyOf
                        sub_prop = next(g.objects(s, RDFS.subPropertyOf), "")
                        sub_prop_val = str(sub_prop).split("#")[-1] if sub_prop else ""
                        
                        # Get subPropertyOf label if it exists
                        sub_prop_label = ""
                        if sub_prop:
                            sub_prop_label = next(g.objects(sub_prop, RDFS.label), sub_prop_val)
                        
                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontologies_oprop", 
                            "title": next(g.objects(s, RDFS.label), str(s).split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ''),
                            "example": next(g.objects(s, SKOS.example), ''),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "domain": domain,
                            "range": range_val,
                            "subPropertyOf": sub_prop_val,
                            "subPropertyOfLabel": sub_prop_label,
                            "image_url": "",
                            "source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}")
                        })
                        
                # Add data properties
                for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty)):
                    if isinstance(s, URIRef):
                        # Get domain
                        domain_obj = next(g.objects(s, RDFS.domain), "")
                        domain = str(domain_obj).split("#")[-1] if domain_obj else ""
                        
                        # Get range 
                        range_obj = next(g.objects(s, RDFS.range), "")
                        range_val = str(range_obj).split("#")[-1] if range_obj else ""

                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontologies_dprop",
                            "title": next(g.objects(s, RDFS.label), str(s).split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ""),
                            "example": next(g.objects(s, SKOS.example), ""),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "domain": domain,
                            "range": range_val,
                            "image_url": "",
                            "source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}")
                        })

                # Add annotation properties
                for s, p, o in g.triples((None, RDF.type, OWL.AnnotationProperty)):
                    if isinstance(s, URIRef):
                        results.append({
                            "objectID": hashlib.sha256(str(s).encode()).hexdigest(),
                            "type": "ontologies_annotation_property", 
                            "title": next(g.objects(s, RDFS.label), str(s).split("#")[-1]).capitalize(),
                            "description": next(g.objects(s, SKOS.definition), ""),
                            "example": next(g.objects(s, SKOS.example), ""),
                            "comment": next(g.objects(s, RDFS.comment), ""),
                            "image_url": "",
                            "source_url": next(g.objects(s, CCO.ont00001760), f"https://github.com/abi/src/ontologies/{file.name}")
                        })
                
            except Exception as e:
                logger.error(f"Error processing ontology {file}: {e}")
        
        return results

    def run(self, parameters: UpdateAlgoliaIndexParameters) -> Dict[str, Any]:
        """Updates the Algolia index with all collected data.
        
        Returns:
            Dict[str, Any]: Summary of the update operation
        """
        all_records = []
        
        # Collect all data
        all_records.extend(self.__scan_assistants())
        all_records.extend(self.__scan_integrations())
        all_records.extend(self.__scan_ontologies())
        
        # Save records to local file for backup
        import json
        import os
        from datetime import datetime

        # Create backup directory if it doesn't exist
        backup_dir = "data/algolia_backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"algolia_records_{timestamp}.json")

        # Save records to JSON file
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(all_records, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(all_records)} records to {backup_file}")

        # Update Algolia index
        result = self.__algolia.update_index(parameters.index_name, all_records)
        
        return {
            "status": "success",
            "records_processed": len(all_records),
            "algolia_response": result
        }

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [StructuredTool(
            name="update_algolia_index",
            description="Updates the Algolia search index with all assistants, integrations, and ontologies metadata",
            func=lambda **kwargs: self.run(UpdateAlgoliaIndexParameters(**kwargs)),
            args_schema=UpdateAlgoliaIndexParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/update_algolia_index")
        def update_algolia_index(parameters: UpdateAlgoliaIndexParameters):
            return self.run(parameters) 