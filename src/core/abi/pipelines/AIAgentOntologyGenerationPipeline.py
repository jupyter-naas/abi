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
        """
        Main pipeline execution with clear steps:
        1. Load Artificial Analysis data
        2. Group models by AI agent
        3. Generate ontologies in timestamped datastore folders
        4. Deploy current versions to module folders
        5. Create audit trail and summary
        """
        if not isinstance(parameters, AIAgentOntologyGenerationParameters):
            raise ValueError("Parameters must be of type AIAgentOntologyGenerationParameters")
        
        # Initialize graph for results
        graph = Graph()
        
        # STEP 1: Load latest Artificial Analysis data
        aa_data = self._load_latest_aa_data()
        if not aa_data:
            raise ValueError("No Artificial Analysis data found")
        
        # STEP 2-5: Process and generate ontologies (includes deployment)
        generated_files = self._execute_pipeline_steps(aa_data, parameters)
        
        # STEP 6: Create summary triples
        pipeline_uri = ABI[f"AIAgentOntologyGeneration_{uuid.uuid4()}"]
        graph.add((pipeline_uri, ABI.hasGeneratedFiles, Literal(len(generated_files))))
        graph.add((pipeline_uri, ABI.hasTimestamp, Literal(datetime.now(timezone.utc).isoformat())))
        
        # Store results in triple store
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
    
    def _execute_pipeline_steps(
        self, 
        aa_data: Dict[str, Any], 
        parameters: AIAgentOntologyGenerationParameters
    ) -> List[Path]:
        """
        Execute the main pipeline steps:
        STEP 2: Extract and group models by AI agent
        STEP 3: Generate ontologies in timestamped datastore folders  
        STEP 4: Deploy current versions to module folders
        STEP 5: Create audit trail and summary
        """
        # STEP 2: Extract and group models by AI agent
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        output_dir = Path(self.__configuration.datastore_path) / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        
        models = aa_data.get('llms', []) or aa_data.get('data', [])
        agent_models = self._group_models_by_agent(models)
        
        # Apply agent filter if specified
        if parameters.agent_filter:
            agent_models = {
                agent: models for agent, models in agent_models.items()
                if agent in parameters.agent_filter
            }
        
        # STEP 3-4: Generate and deploy ontologies for each agent
        generated_files = []
        for agent_module, models in agent_models.items():
            agent_files = self._process_single_agent(
                agent_module, models, timestamp, output_dir
            )
            generated_files.extend(agent_files)
        
        # STEP 5: Create summary and audit trail
        self._create_execution_summary(
            timestamp, models, agent_models, generated_files, output_dir
        )
        
        return generated_files
    
    def _process_single_agent(
        self, 
        agent_module: str, 
        models: List[Dict[str, Any]], 
        timestamp: str, 
        output_dir: Path
    ) -> List[Path]:
        """Process a single AI agent: generate ontology content and deploy to multiple locations."""
        # Limit models per agent if configured
        if len(models) > self.__configuration.max_models_per_agent:
            models = models[:self.__configuration.max_models_per_agent]
        
        # Generate ontology content
        ontology_content = self._generate_agent_ontology_file(agent_module, models)
        agent_title = agent_module.replace('_', '').title()
        
        # File paths
        current_filename = f"{agent_title}Ontology.ttl"
        audit_filename = f"{timestamp}_{agent_title}Ontology.ttl"
        
        generated_files = []
        
        # STEP 3A: Write current version to datastore (for deployment)
        current_file = output_dir / current_filename
        with open(current_file, 'w', encoding='utf-8') as f:
            f.write(ontology_content)
        generated_files.append(current_file)
        
        # STEP 3B: Write audit version to datastore (for history)
        audit_file = output_dir / audit_filename
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write(ontology_content)
        generated_files.append(audit_file)
        
        # STEP 4: Deploy current version to module folder
        # From pipelines/ go up 3 levels to reach modules/
        modules_dir = Path(__file__).parent.parent.parent  # Go up 3 levels to /Users/jrvmac/abi/src/core/modules
        module_dir = modules_dir / agent_module / "ontologies"
        
        # Create module directory if it doesn't exist
        module_dir.mkdir(parents=True, exist_ok=True)
        
        # Deploy to module folder
        module_file = module_dir / current_filename
        with open(module_file, 'w', encoding='utf-8') as f:
            f.write(ontology_content)
        generated_files.append(module_file)
        
        return generated_files
    
    def _create_execution_summary(
        self, 
        timestamp: str, 
        models: List[Dict[str, Any]], 
        agent_models: Dict[str, List[Dict[str, Any]]], 
        generated_files: List[Path], 
        output_dir: Path
    ) -> None:
        """Create execution summary for audit trail."""
        summary_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": timestamp,
            "total_models_processed": len(models),
            "agents_generated": len(agent_models),
            "total_files_generated": len(generated_files),
            "agent_breakdown": {agent: len(models) for agent, models in agent_models.items()},
            "file_locations": {
                "datastore_current": [str(f) for f in generated_files if "datastore" in str(f) and not f.name.startswith("2")],
                "datastore_audit": [str(f) for f in generated_files if "datastore" in str(f) and f.name.startswith("2")],
                "module_deployed": [str(f) for f in generated_files if "src/core/modules" in str(f)]
            }
        }
        
        summary_file = output_dir / f"generation_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
    
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
        """Generate BFO-structured ontology from Artificial Analysis JSON.
        
        JSON MAPPING TO BFO 7 BUCKETS:
        
        Bucket 1 (Material Entities): 
        - JSON 'name' → abi:AIModelInstance 
        - JSON 'model_creator.name' → abi:provider
        
        Bucket 2 (Qualities):
        - JSON 'pricing.*' → abi:*TokenCost properties
        - JSON 'median_*' → abi:outputSpeed, timeToFirstToken
        - JSON 'evaluations.*' → abi:intelligenceIndex, codingIndex, mathIndex
        
        Bucket 3 (Realizable Entities):
        - Imported from CapabilityOntology → capability:TextGenerationCapability, etc.
        
        Bucket 4 (Processes):
        - Generated process instances → abi:BusinessProposalCreationProcess, etc.
        
        Bucket 5 (Temporal Regions):
        - Generated session instances → abi:InferenceSession
        
        Bucket 6 (Spatial Regions):
        - Inherited from AIAgentOntology → abi:DataCenterLocation
        
        Bucket 7 (Information Content):
        - JSON 'sourceAPI' → abi:sourceAPI property
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        agent_title = agent_module.replace('_', '').title()
        
        # Generate ontology content following BFO 7 buckets structure
        ontology_content = f"""@prefix abi: <http://naas.ai/ontology/abi#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix capability: <http://ontology.naas.ai/abi/capability/> .
@prefix dc: <http://purl.org/dc/terms/> .

<http://naas.ai/ontology/abi/{agent_title}Ontology> a owl:Ontology ;
    owl:imports <http://ontology.naas.ai/abi/AIAgentOntology> ;
    dc:title "{agent_title} AI Agent Ontology"@en ;
    dc:description "BFO-grounded ontology for {agent_title} AI models and processes"@en ;
    dc:created "{timestamp}"@en .

"""
        
        # BFO Bucket 1: Material Entity (WHAT/WHO) - The AI Agent
        agent_uri = f"abi:{agent_title}Agent"
        ontology_content += f"""
#################################################################
#    BFO Bucket 1: Material Entities (WHAT/WHO)
#################################################################

{agent_uri} a abi:AIAgent ;
    rdfs:label "{agent_title} AI Agent"@en ;
    rdfs:comment "AI Agent capable of utilizing {agent_title} models"@en ;
    abi:hasSpecializedRole "Multi-purpose AI processing"@en .

"""
        
        # Add BFO Process Instances for this agent
        process_mappings = self._generate_process_mappings(agent_title, agent_uri)
        ontology_content += process_mappings
        
        # Add models
        for i, model in enumerate(models):
            model_content = self._generate_model_instance(model, agent_uri, i)
            ontology_content += model_content + "\n"
        
        return ontology_content
    
    def _generate_process_mappings(self, agent_title: str, agent_uri: str) -> str:
        """Generate BFO process instances following the 7 buckets framework."""
        process_content = f"""
#################################################################
#    BFO Bucket 4: Processes (HOW-IT-HAPPENS)
#################################################################

abi:{agent_title}BusinessProposalProcess a abi:BusinessProposalCreationProcess ;
    rdfs:label "{agent_title} Business Proposal Process"@en ;
    abi:hasParticipant {agent_uri} ;
    abi:realizesCapability capability:TextGenerationCapability ;
    abi:hasTemporalRegion abi:{agent_title}BusinessProposalSession ;
    abi:hasQuality abi:{agent_title}BusinessProposalQuality .

abi:{agent_title}CreativeWritingProcess a abi:CreativeWritingProcess ;
    rdfs:label "{agent_title} Creative Writing Process"@en ;
    abi:hasParticipant {agent_uri} ;
    abi:realizesCapability capability:TextGenerationCapability ;
    abi:hasTemporalRegion abi:{agent_title}CreativeWritingSession ;
    abi:hasQuality abi:{agent_title}CreativeWritingQuality .

abi:{agent_title}CodeGenerationProcess a abi:CodeGenerationProcess ;
    rdfs:label "{agent_title} Code Generation Process"@en ;
    abi:hasParticipant {agent_uri} ;
    abi:realizesCapability capability:CodeGenerationCapability ;
    abi:hasTemporalRegion abi:{agent_title}CodeGenerationSession ;
    abi:hasQuality abi:{agent_title}CodeGenerationQuality .

#################################################################
#    BFO Bucket 5: Temporal Regions (WHEN)
#################################################################

abi:{agent_title}BusinessProposalSession a abi:InferenceSession ;
    rdfs:label "{agent_title} Business Proposal Session"@en .

abi:{agent_title}CreativeWritingSession a abi:InferenceSession ;
    rdfs:label "{agent_title} Creative Writing Session"@en .

abi:{agent_title}CodeGenerationSession a abi:InferenceSession ;
    rdfs:label "{agent_title} Code Generation Session"@en .

"""
        return process_content
    
    def _generate_model_instance(self, model: Dict[str, Any], agent_uri: str, index: int) -> str:
        """Generate BFO-structured model instance from Artificial Analysis JSON."""
        
        # JSON → BFO Bucket 1: Material Entity extraction
        model_name = model.get('name', 'Unknown Model')
        model_slug = model.get('slug', 'unknown')
        model_id = self._generate_uri_safe_id(model_name)
        creator = model.get('model_creator', {})
        creator_name = creator.get('name', 'Unknown')
        
        # JSON → BFO Bucket 2: Qualities extraction
        pricing = model.get('pricing', {})
        input_cost = pricing.get('price_1m_input_tokens') or 0
        output_cost = pricing.get('price_1m_output_tokens') or 0
        blended_cost = pricing.get('price_1m_blended_3_to_1') or 0
        
        output_speed = model.get('median_output_tokens_per_second') or 0
        ttft = model.get('median_time_to_first_token_seconds') or 0
        ttft_answer = model.get('median_time_to_first_answer_token') or 0
        
        evaluations = model.get('evaluations', {})
        intelligence_index = evaluations.get('artificial_analysis_intelligence_index') or 0
        coding_index = evaluations.get('artificial_analysis_coding_index') or 0
        math_index = evaluations.get('artificial_analysis_math_index') or 0
        
        agent_title = agent_uri.replace('abi:', '').replace('Agent', '')
        
        return f"""
#################################################################
#    BFO Bucket 1: Material Entity - {model_name}
#################################################################

abi:{model_id} a abi:AIModelInstance ;
    rdfs:label "{model_name}"@en ;
    abi:modelSlug "{model_slug}"@en ;
    abi:provider "{creator_name}"@en ;
    abi:sourceAPI "artificial_analysis"@en .

#################################################################
#    BFO Bucket 2: Qualities - Performance & Cost Metrics
#################################################################

abi:{model_id} abi:inputTokenCost {input_cost} ;
    abi:inputTokenCostCurrency "USD"@en ;
    abi:outputTokenCost {output_cost} ;
    abi:outputTokenCostCurrency "USD"@en ;
    abi:blendedCost {blended_cost} ;
    abi:blendedCostCurrency "USD"@en ;
    abi:outputSpeed {output_speed} ;
    abi:outputSpeedUnit "tokens_per_second"@en ;
    abi:timeToFirstToken {ttft} ;
    abi:timeToFirstTokenUnit "seconds"@en ;
    abi:timeToFirstAnswerToken {ttft_answer} ;
    abi:timeToFirstAnswerTokenUnit "seconds"@en ;
    abi:intelligenceIndex {intelligence_index} ;
    abi:codingIndex {coding_index} ;
    abi:mathIndex {math_index} .

#################################################################
#    Relationships - Agent/Process/Model Network
#################################################################

{agent_uri} abi:canUtilizeModel abi:{model_id} .
abi:{agent_title}BusinessProposalProcess abi:utilizesModel abi:{model_id} .
abi:{agent_title}CreativeWritingProcess abi:utilizesModel abi:{model_id} .
abi:{agent_title}CodeGenerationProcess abi:utilizesModel abi:{model_id} ."""
    
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
                description="Generates AI agent ontologies from Artificial Analysis data (datastore only, no module deployment)",
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


# =============================================================================
# PIPELINE EXECUTION SUMMARY
# =============================================================================
"""
AI Agent Ontology Generation Pipeline

OVERVIEW:
This pipeline generates AI agent ontologies from Artificial Analysis data,
creates proper audit trails, and deploys current versions to module folders.

EXECUTION STEPS:
1. Load Artificial Analysis data from datastore
2. Extract and group models by AI agent family
3. Generate ontology content for each agent
4. Deploy to structured locations:
   - Datastore: timestamped folders with current + audit versions
   - Modules: current versions only for immediate use

FILE STRUCTURE CREATED:
📁 storage/datastore/core/modules/abi/AIAgentOntologyGenerationPipeline/
├── 📁 YYYYMMDDTHHMMSS/
│   ├── 📄 ClaudeOntology.ttl (current - for deployment)
│   ├── 📄 YYYYMMDDTHHMMSS_ClaudeOntology.ttl (audit - for history)
│   ├── 📄 ChatgptOntology.ttl (current - for deployment)
│   ├── 📄 YYYYMMDDTHHMMSS_ChatgptOntology.ttl (audit - for history)
│   └── 📄 generation_summary_YYYYMMDDTHHMMSS.json
└── ...

📁 src/core/modules/
├── 📁 claude/ontologies/ClaudeOntology.ttl (deployed current version)
├── 📁 chatgpt/ontologies/ChatgptOntology.ttl (deployed current version)
└── ...

BENEFITS:
✅ Single pipeline handles everything (generation + deployment)
✅ Complete audit trail with timestamped versions
✅ Current versions always available in module folders
✅ Clean separation of concerns with organized methods
✅ Comprehensive execution summaries for monitoring
"""
