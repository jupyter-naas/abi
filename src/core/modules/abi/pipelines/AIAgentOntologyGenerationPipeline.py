from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from rdflib import Graph, Namespace, Literal
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class AIAgentOntologyGenerationConfiguration(PipelineConfiguration):
    """Configuration for AI Agent Ontology Generation Pipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
        datastore_path (str): Path to store generated ontology files
        source_datastore_path (str): Path to source Artificial Analysis data
        max_models_per_agent (int): Maximum models per agent for performance
    """
    triple_store: ITripleStoreService
    datastore_path: str = "storage/datastore/core/modules/abi/AIAgentOntologyGenerationPipeline"
    source_datastore_path: str = "storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow"
    max_models_per_agent: int = 50

class AIAgentOntologyGenerationParameters(PipelineParameters):
    """Parameters for AI Agent Ontology Generation Pipeline execution.
    
    Attributes:
        force_regenerate (bool): Force regeneration even if files exist
        agent_filter (List[str]): Filter specific agents to generate
    """
    force_regenerate: bool = False
    agent_filter: Optional[List[str]] = None

class AIAgentOntologyGenerationPipeline(Pipeline):
    __configuration: AIAgentOntologyGenerationConfiguration
    
    def __init__(self, configuration: AIAgentOntologyGenerationConfiguration):
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AIAgentOntologyGenerationParameters):
            raise ValueError("Parameters must be of type AIAgentOntologyGenerationParameters")
        
        # Init graph
        graph = Graph()
        
        # Load latest Artificial Analysis data
        aa_data = self._load_latest_aa_data()
        if not aa_data:
            raise ValueError("No Artificial Analysis data found")
        
        # Process models and generate ontologies
        generated_files = self._process_and_generate_ontologies(aa_data, parameters)
        
        # Create summary triples in the graph
        pipeline_uri = ABI[f"AIAgentOntologyGeneration_{uuid.uuid4()}"]
        graph.add((pipeline_uri, ABI.hasGeneratedFiles, Literal(len(generated_files))))
        graph.add((pipeline_uri, ABI.hasTimestamp, Literal(datetime.now(timezone.utc).isoformat())))
        
        # Store the graph in the ontology store
        self.__configuration.triple_store.insert(graph)
        
        return graph
    
    def _load_latest_aa_data(self) -> Optional[Dict[str, Any]]:
        """Load the latest Artificial Analysis data from datastore."""
        aa_dir = Path(self.__configuration.source_datastore_path)
        
        if not aa_dir.exists():
            return None
        
        # Find latest JSON file
        json_files = list(aa_dir.glob("*_llms_data.json"))
        if not json_files:
            return None
        
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _process_and_generate_ontologies(
        self, 
        aa_data: Dict[str, Any], 
        parameters: AIAgentOntologyGenerationParameters
    ) -> List[Path]:
        """Process AA data and generate ontology files."""
        # Ensure output directory exists
        output_dir = Path(self.__configuration.datastore_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract models from data (support both old 'llms' and new 'data' formats)
        models = aa_data.get('llms', []) or aa_data.get('data', [])
        
        # Group models by AI agent module
        agent_models: Dict[str, List[Dict[str, Any]]] = self._group_models_by_agent(models)
        
        # Apply filters if specified
        if parameters.agent_filter:
            agent_models = {
                agent: models for agent, models in agent_models.items()
                if agent in parameters.agent_filter
            }
        
        # Generate ontologies
        generated_files = []
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        
        for agent_module, models in agent_models.items():
            # Limit models per agent if configured
            if len(models) > self.__configuration.max_models_per_agent:
                models = models[:self.__configuration.max_models_per_agent]
            
            # Generate ontology content
            ontology_content = self._generate_agent_ontology_file(agent_module, models)
            
            # Write to file with proper naming convention
            agent_title = agent_module.replace('_', '').title()  # Convert gpt_oss to GptOss
            filename = f"{timestamp}_{agent_title}Ontology.ttl"
            output_file = output_dir / filename
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(ontology_content)
            
            generated_files.append(output_file)
        
        # Generate summary
        summary_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_models_processed": len(models),
            "agents_generated": len(agent_models),
            "agent_breakdown": {agent: len(models) for agent, models in agent_models.items()},
            "generated_files": [str(f.relative_to(output_dir)) for f in generated_files]
        }
        
        summary_file = output_dir / f"generation_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
        
        return generated_files
    
    def _group_models_by_agent(self, models: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group models by AI agent module based on model family."""
        agent_models: Dict[str, List[Dict[str, Any]]] = {}
        
        for model in models:
            agent_module = self._determine_ai_agent_module(model)
            
            if agent_module:
                if agent_module not in agent_models:
                    agent_models[agent_module] = []
                agent_models[agent_module].append(model)
        
        return agent_models
    
    def _determine_ai_agent_module(self, model_data: Dict[str, Any]) -> Optional[str]:
        """Map model to AI agent module based on model name/slug, not just provider."""
        model_name = model_data.get('name', '').lower()
        model_slug = model_data.get('slug', '').lower()
        creator = model_data.get('model_creator', {})
        creator_name = creator.get('name', '').lower()
        creator_slug = creator.get('slug', '').lower()
        
        # Model family to module mapping (prioritizing model name over provider)
        model_mapping = {
            # OpenAI models
            'gpt': 'chatgpt',
            'chatgpt': 'chatgpt', 
            'o1': 'chatgpt',
            'o3': 'chatgpt',
            'o4': 'chatgpt',
            'gpt-4': 'chatgpt',
            'gpt-5': 'chatgpt',
            'davinci': 'chatgpt',
            
            # OpenAI Open Source models (different from ChatGPT)
            'gpt-oss': 'gpt_oss',
            'gpt_oss': 'gpt_oss',
            
            # Anthropic
            'claude': 'claude',
            
            # Google models - separate by family
            'gemini': 'gemini',
            'gemma': 'gemma',
            'palm': 'gemini',  # Palm is part of Gemini family
            
            # Meta/Facebook
            'llama': 'llama',
            'meta': 'llama',
            
            # xAI
            'grok': 'grok',
            
            # Mistral
            'mistral': 'mistral',
            'mixtral': 'mistral',
            'codestral': 'mistral',
            
            # DeepSeek
            'deepseek': 'deepseek',
            
            # Alibaba
            'qwen': 'qwen',
            'qwq': 'qwen',
            
            # Perplexity
            'sonar': 'perplexity',
            'perplexity': 'perplexity',
            
            # Other model families
            'phi': 'phi',
            'titan': 'titan',
            'yi': 'yi',
            'solar': 'solar',
            'exaone': 'exaone',
            'glm': 'glm',
            'minimax': 'minimax',
            'kimi': 'kimi',
            'arctic': 'arctic',
            'dbrx': 'dbrx',
            'lfm': 'lfm',
            'cohere': 'cohere',
            'command': 'cohere',
            'jamba': 'jamba',
            'reka': 'reka',
            'openchat': 'openchat',
            'tulu': 'tulu',
            'nous': 'nous_research',
            'hermes': 'nous_research'
        }
        
        # Check model name/slug first for family identification
        for pattern, module in model_mapping.items():
            if pattern in model_name or pattern in model_slug:
                return module
        
        # Fallback to provider-based mapping for unmapped models
        provider_mapping = {
            'openai': 'chatgpt',
            'anthropic': 'claude',
            'google': 'gemini',  # Default Google to Gemini if no specific family found
            'x.ai': 'grok',
            'xai': 'grok',
            'mistral ai': 'mistral',
            'mistral': 'mistral',
            'meta': 'llama',
            'deepseek': 'deepseek',
            'perplexity': 'perplexity',
            'alibaba': 'qwen'
        }
        
        # Try provider match as fallback
        for provider, module in provider_mapping.items():
            if provider in creator_name or provider in creator_slug:
                return module
        
        return None
    
    def _generate_agent_ontology_file(self, agent_module: str, models: List[Dict[str, Any]]) -> str:
        """Generate complete ontology file for an AI agent and its models."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        agent_title = agent_module.replace('_', '').title()
        
        # Generate ontology content
        ontology_content = f"""@prefix abi: <http://naas.ai/ontology/abi#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2001/XMLSchema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix bfo: <http://purl.obolibrary.org/obo/BFO_> .

# {agent_title} AI Agent Ontology
# Generated on: {timestamp}
# Models: {len(models)}

"""
        
        # Add AI Agent definition
        agent_uri = f"abi:{agent_title}Agent"
        ontology_content += f"""# AI Agent Definition
{agent_uri} a abi:AIAgent ;
    rdfs:label "{agent_title} AI Agent"@en ;
    rdfs:comment "AI Agent capable of utilizing {agent_title} family models for various processes"@en ;
    abi:hasSpecializedRole "Multi-purpose AI processing and reasoning"@en .

"""
        
        # Add models
        for i, model in enumerate(models):
            model_content = self._generate_model_instance(model, agent_uri, i)
            ontology_content += model_content + "\n"
        
        return ontology_content
    
    def _generate_model_instance(self, model: Dict[str, Any], agent_uri: str, index: int) -> str:
        """Generate ontology content for a single model instance."""
        # Extract model data
        model_name = model.get('name', 'Unknown Model')
        model_slug = model.get('slug', 'unknown')
        model_id = self._generate_uri_safe_id(model_name)
        
        creator = model.get('model_creator', {})
        creator_name = creator.get('name', 'Unknown')
        
        # Pricing data
        pricing = model.get('pricing', {})
        input_cost = pricing.get('input_cost') or 0
        output_cost = pricing.get('output_cost') or 0
        
        # Performance data
        performance = model.get('performance', {})
        output_speed = performance.get('output_speed') or 0
        ttft = performance.get('time_to_first_token') or 0
        ttft_answer = performance.get('time_to_first_answer_token') or 0
        
        # Evaluation data
        evaluations = model.get('evaluations', {})
        intelligence_index = evaluations.get('index') or 0
        coding_index = evaluations.get('coding_index') or 0
        math_index = evaluations.get('math_index') or 0
        
        return f"""# Model Instance: {model_name}
abi:{model_id} a abi:AIModelInstance ;
    rdfs:label "{model_name}"@en ;
    rdfs:comment "AI model instance with specific capabilities and performance characteristics"@en ;
    abi:modelSlug "{model_slug}"@en ;
    abi:provider "{creator_name}"@en ;
    abi:inputTokenCost {input_cost} ;
    abi:inputTokenCostCurrency "USD"@en ;
    abi:outputTokenCost {output_cost} ;
    abi:outputTokenCostCurrency "USD"@en ;
    abi:blendedCostCurrency "USD"@en ;
    abi:outputSpeed {output_speed} ;
    abi:outputSpeedUnit "tokens_per_second"@en ;
    abi:timeToFirstToken {ttft} ;
    abi:timeToFirstTokenUnit "seconds"@en ;
    abi:timeToFirstAnswerToken {ttft_answer} ;
    abi:timeToFirstAnswerTokenUnit "seconds"@en ;
    abi:intelligenceIndex {intelligence_index} ;
    abi:codingIndex {coding_index} ;
    abi:mathIndex {math_index} ;
    abi:sourceAPI "artificial_analysis"@en .

{agent_uri} abi:canUtilizeModel abi:{model_id} ."""
    
    def _generate_uri_safe_id(self, text: str) -> str:
        """Generate URI-safe identifier from text."""
        # Replace spaces and special characters with underscores
        safe_id = text.replace(' ', '_').replace('-', '_').replace('.', '_')
        safe_id = safe_id.replace('(', '').replace(')', '').replace("'", '')
        safe_id = safe_id.replace('/', '_').replace('\\', '_')
        # Remove consecutive underscores
        while '__' in safe_id:
            safe_id = safe_id.replace('__', '_')
        # Remove leading/trailing underscores
        safe_id = safe_id.strip('_')
        return safe_id
    
    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[BaseTool]: List containing the pipeline tool
        """
        return [
            StructuredTool(
                name="ai_agent_ontology_generation",
                description="Generates AI agent ontologies from Artificial Analysis data",
                func=lambda **kwargs: self.run(AIAgentOntologyGenerationParameters(**kwargs)),
                args_schema=AIAgentOntologyGenerationParameters
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
    
    def get_configuration(self) -> AIAgentOntologyGenerationConfiguration:
        """Get the pipeline configuration."""
        return self.__configuration
