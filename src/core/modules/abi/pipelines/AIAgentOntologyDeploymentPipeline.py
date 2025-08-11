from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from pydantic import BaseModel
from rdflib import Graph, Namespace, Literal
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import shutil

ABI = Namespace("http://ontology.naas.ai/abi/")

class EmptyParameters(BaseModel):
    """Empty parameters for tools that don't need input."""
    pass

@dataclass
class AIAgentOntologyDeploymentConfiguration(PipelineConfiguration):
    """Configuration for AI Agent Ontology Deployment Pipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
        source_datastore_path (str): Path to source generated ontology files
        target_modules_path (str): Base path to module directories
    """
    triple_store: ITripleStoreService
    source_datastore_path: str = "storage/datastore/core/modules/abi/AIAgentOntologyGenerationPipeline"
    target_modules_path: str = "src/core/modules"

class AIAgentOntologyDeploymentParameters(PipelineParameters):
    """Parameters for AI Agent Ontology Deployment Pipeline execution.
    
    Attributes:
        timestamp_filter (str): Deploy only files with specific timestamp (YYYYMMDDTHHMMSS)
        agent_filter (List[str]): Deploy only specific agents
        overwrite_existing (bool): Whether to overwrite existing ontology files
        cleanup_old (bool): Remove old ontology files before deploying new ones
    """
    timestamp_filter: Optional[str] = None
    agent_filter: Optional[List[str]] = None
    overwrite_existing: bool = True
    cleanup_old: bool = False

class AIAgentOntologyDeploymentPipeline(Pipeline):
    __configuration: AIAgentOntologyDeploymentConfiguration
    
    def __init__(self, configuration: AIAgentOntologyDeploymentConfiguration):
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AIAgentOntologyDeploymentParameters):
            raise ValueError("Parameters must be of type AIAgentOntologyDeploymentParameters")
        
        # Init graph
        graph = Graph()
        
        # Find ontology files to deploy
        source_files = self._find_source_files(parameters)
        if not source_files:
            raise ValueError("No ontology files found to deploy")
        
        # Deploy files to module directories
        deployed_files = self._deploy_files(source_files, parameters)
        
        # Create summary triples in the graph
        deployment_uri = ABI[f"AIAgentOntologyDeployment_{uuid.uuid4()}"]
        graph.add((deployment_uri, ABI.hasDeployedFiles, Literal(len(deployed_files))))
        graph.add((deployment_uri, ABI.hasTimestamp, Literal(datetime.now(timezone.utc).isoformat())))
        
        # Store the graph in the ontology store
        self.__configuration.triple_store.insert(graph)
        
        return graph
    
    def _find_source_files(self, parameters: AIAgentOntologyDeploymentParameters) -> List[Path]:
        """Find ontology files to deploy based on parameters."""
        source_dir = Path(self.__configuration.source_datastore_path)
        
        if not source_dir.exists():
            return []
        
        # Find all ontology files
        ontology_files = list(source_dir.glob("*Ontology.ttl"))
        
        # Apply timestamp filter
        if parameters.timestamp_filter:
            ontology_files = [
                f for f in ontology_files 
                if f.name.startswith(parameters.timestamp_filter)
            ]
        
        # Apply agent filter
        if parameters.agent_filter:
            filtered_files = []
            for agent in parameters.agent_filter:
                agent_title = agent.replace('_', '').title()
                agent_files = [
                    f for f in ontology_files 
                    if f.name.endswith(f"{agent_title}Ontology.ttl")
                ]
                filtered_files.extend(agent_files)
            ontology_files = filtered_files
        
        return sorted(ontology_files)
    
    def _deploy_files(
        self, 
        source_files: List[Path], 
        parameters: AIAgentOntologyDeploymentParameters
    ) -> List[Path]:
        """Deploy ontology files to their respective module directories."""
        deployed_files = []
        modules_base = Path(self.__configuration.target_modules_path)
        
        for source_file in source_files:
            # Extract agent name from filename
            agent_name = self._extract_agent_name_from_filename(source_file.name)
            if not agent_name:
                continue
            
            # Determine target module directory
            target_module_dir = modules_base / agent_name / "ontologies"
            
            if not target_module_dir.exists():
                # Create module ontology directory if it doesn't exist
                target_module_dir.mkdir(parents=True, exist_ok=True)
            
            # Clean up old files if requested
            if parameters.cleanup_old:
                self._cleanup_old_files(target_module_dir, agent_name)
            
            # Deploy file
            target_file = target_module_dir / source_file.name
            
            if target_file.exists() and not parameters.overwrite_existing:
                continue  # Skip if file exists and overwrite is disabled
            
            shutil.copy2(source_file, target_file)
            deployed_files.append(target_file)
        
        return deployed_files
    
    def _extract_agent_name_from_filename(self, filename: str) -> Optional[str]:
        """Extract agent name from ontology filename."""
        # Expected format: YYYYMMDDTHHMMSS_{Agent}Ontology.ttl
        if not filename.endswith("Ontology.ttl"):
            return None
        
        parts = filename.split("_")
        if len(parts) < 2:
            return None
        
        # Extract agent name (remove "Ontology.ttl")
        agent_part = parts[1].replace("Ontology.ttl", "")
        
        # Convert from title case back to module name
        # ChatgptOntology -> chatgpt
        return agent_part.lower()
    
    def _cleanup_old_files(self, target_dir: Path, agent_name: str) -> None:
        """Remove old ontology files for the agent."""
        agent_title = agent_name.replace('_', '').title()
        old_files = list(target_dir.glob(f"*{agent_title}Ontology.ttl"))
        
        for old_file in old_files:
            old_file.unlink()
    
    def get_latest_timestamp(self) -> Optional[str]:
        """Get the latest timestamp available for deployment."""
        source_dir = Path(self.__configuration.source_datastore_path)
        
        if not source_dir.exists():
            return None
        
        ontology_files = list(source_dir.glob("*Ontology.ttl"))
        if not ontology_files:
            return None
        
        # Extract timestamps and find the latest
        timestamps = []
        for file in ontology_files:
            parts = file.name.split("_")
            if len(parts) >= 2:
                timestamps.append(parts[0])
        
        return max(timestamps) if timestamps else None
    
    def list_available_deployments(self) -> Dict[str, List[str]]:
        """List available ontology files grouped by timestamp."""
        source_dir = Path(self.__configuration.source_datastore_path)
        
        if not source_dir.exists():
            return {}
        
        ontology_files = list(source_dir.glob("*Ontology.ttl"))
        deployments: Dict[str, List[str]] = {}
        
        for file in ontology_files:
            parts = file.name.split("_")
            if len(parts) >= 2:
                timestamp = parts[0]
                agent = self._extract_agent_name_from_filename(file.name)
                
                if timestamp not in deployments:
                    deployments[timestamp] = []
                if agent:
                    deployments[timestamp].append(agent)
        
        return deployments
    
    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[BaseTool]: List containing the pipeline tools
        """
        return [
            StructuredTool(
                name="deploy_ai_agent_ontologies",
                description="Deploys AI agent ontologies from datastore to module folders",
                func=lambda **kwargs: self.run(AIAgentOntologyDeploymentParameters(**kwargs)),
                args_schema=AIAgentOntologyDeploymentParameters
            ),
            StructuredTool(
                name="list_available_deployments", 
                description="Lists available ontology deployments by timestamp",
                func=lambda: self.list_available_deployments(),
                args_schema=EmptyParameters
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
    
    def get_configuration(self) -> AIAgentOntologyDeploymentConfiguration:
        """Get the pipeline configuration."""
        return self.__configuration
