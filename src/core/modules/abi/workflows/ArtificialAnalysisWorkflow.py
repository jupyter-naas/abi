"""
Artificial Analysis Integration Workflow

Fetches AI model performance data from Artificial Analysis API and generates
ontology files for each AI agent module with capabilities and performance metrics.
"""

import requests
import pandas as pd
from typing import Dict, List, Any
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import StructuredTool, BaseTool
from pydantic import BaseModel, Field

from lib.abi.workflow import WorkflowConfiguration


@dataclass
class ArtificialAnalysisWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Artificial Analysis API integration."""
    
    api_key: str = Field(description="Artificial Analysis API key")
    base_url: str = Field(
        default="https://artificialanalysis.ai/api/v2",
        description="Base URL for Artificial Analysis API"
    )
    output_dir: str = Field(
        default="src/core/modules",
        description="Base directory for generating ontology files"
    )


class ArtificialAnalysisParameters(BaseModel):
    """Parameters for Artificial Analysis data fetching."""
    
    endpoint: str = Field(
        default="llms",
        description="API endpoint to fetch (llms, text-to-image, etc.)"
    )
    include_categories: bool = Field(
        default=False,
        description="Include category breakdowns for media endpoints"
    )
    generate_ontologies: bool = Field(
        default=True,
        description="Generate ontology files for each model"
    )


class ArtificialAnalysisWorkflow:
    """Workflow for integrating Artificial Analysis data into ABI ontology system."""
    
    def __init__(self, config: ArtificialAnalysisWorkflowConfiguration):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'x-api-key': config.api_key,
            'Content-Type': 'application/json'
        })
    
    def fetch_models_data(self, endpoint: str = "llms", include_categories: bool = False) -> Dict[str, Any]:
        """Fetch model data from Artificial Analysis API."""
        try:
            if endpoint == "llms":
                url = f"{self.config.base_url}/data/llms/models"
            else:
                url = f"{self.config.base_url}/data/media/{endpoint}"
                if include_categories:
                    url += "?include_categories=true"
            
            print(f"🔍 Fetching data from: {url}")
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ Successfully fetched {len(data.get('data', []))} models from {endpoint}")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching data from Artificial Analysis API: {e}")
            return {"status": "error", "data": []}
    
    def map_llm_to_capabilities(self, model_data: Dict[str, Any]) -> List[str]:
        """Map LLM performance metrics to capability types."""
        capabilities = []
        evaluations = model_data.get('evaluations', {})
        
        # Core text capabilities
        capabilities.append('capability:TextGenerationCapability')
        capabilities.append('capability:ReasoningCapability')
        
        # Specialized capabilities based on performance scores (handle None values)
        coding_index = evaluations.get('artificial_analysis_coding_index') or 0
        math_index = evaluations.get('artificial_analysis_math_index') or 0
        intelligence_index = evaluations.get('artificial_analysis_intelligence_index') or 0
        
        if coding_index > 50:
            capabilities.append('capability:CodeGenerationCapability')
        
        if math_index > 60:
            capabilities.append('capability:ReasoningCapability')
        
        if intelligence_index > 70:
            capabilities.append('capability:TruthSeekingCapability')
        
        return capabilities
    
    def map_media_to_capabilities(self, model_data: Dict[str, Any], endpoint: str) -> List[str]:
        """Map media model performance to capability types."""
        capabilities = []
        
        if endpoint == "text-to-image":
            capabilities.append('capability:ImageGenerationCapability')
        elif endpoint == "text-to-speech":
            capabilities.append('capability:SpeechGenerationCapability')
        elif endpoint == "text-to-video":
            capabilities.append('capability:VideoGenerationCapability')
        elif endpoint == "image-editing":
            capabilities.append('capability:ImageAnalysisCapability')
        elif endpoint == "image-to-video":
            capabilities.append('capability:VideoGenerationCapability')
        
        return capabilities
    
    def determine_model_provider_module(self, model_creator: Dict[str, Any]) -> str:
        """Determine which model provider module this model belongs to based on exact module structure."""
        creator_name = model_creator.get('name', '').lower()
        creator_slug = model_creator.get('slug', '').lower()
        
        # Map to actual existing module directories in src/core/modules/
        if 'openai' in creator_slug or 'gpt' in creator_name.lower():
            return 'chatgpt'  # Module is 'chatgpt', not 'openai'
        elif 'anthropic' in creator_slug or 'claude' in creator_name.lower():
            return 'claude'  # Module is 'claude'
        elif 'mistral' in creator_slug or 'mistral' in creator_name.lower():
            return 'mistral'
        elif 'grok' in creator_slug or 'xai' in creator_slug or 'x.ai' in creator_name.lower():
            return 'grok'
        elif 'google' in creator_slug or 'gemini' in creator_name.lower():
            return 'gemini'  # Module is 'gemini', not 'google'
        elif 'perplexity' in creator_slug or 'perplexity' in creator_name.lower():
            return 'perplexity'
        elif 'meta' in creator_slug or 'llama' in creator_name.lower():
            return 'llama'
        elif 'qwen' in creator_slug or 'alibaba' in creator_name.lower():
            return 'qwen'
        elif 'deepseek' in creator_slug or 'deepseek' in creator_name.lower():
            return 'deepseek'
        elif 'gemma' in creator_slug or 'gemma' in creator_name.lower():
            return 'gemma'
        else:
            # Create generic module for unknown providers using creator slug
            return creator_slug.replace('-', '_').replace('.', '_') or 'unknown'
    
    def extract_model_processes_mapping(self, model_data: Dict[str, Any], endpoint: str) -> List[str]:
        """Extract which AI processes this model can help realize based on its capabilities."""
        processes = []
        
        if endpoint == "llms":
            evaluations = model_data.get('evaluations', {})
            
            # All LLMs can do basic text generation
            processes.append('abi:TextGenerationProcess')
            
            # Specialized processes based on performance thresholds (handle None values)
            coding_index = evaluations.get('artificial_analysis_coding_index') or 0
            math_index = evaluations.get('artificial_analysis_math_index') or 0
            intelligence_index = evaluations.get('artificial_analysis_intelligence_index') or 0
            
            if coding_index > 60:
                processes.append('abi:CodeGenerationProcess')
            
            if intelligence_index > 75:
                processes.append('abi:TruthSeekingAnalysisProcess')
                
            if intelligence_index > 70:
                processes.append('abi:CreativeWritingProcess')
                
            # If model has strong reasoning scores, it can do ethical analysis
            if intelligence_index > 65 and math_index > 70:
                processes.append('abi:EthicalAnalysisProcess')
                
        elif endpoint == "text-to-image":
            processes.append('abi:ImageGenerationProcess')
        elif endpoint == "text-to-speech":
            processes.append('abi:SpeechGenerationProcess')
        elif endpoint == "text-to-video":
            processes.append('abi:VideoGenerationProcess')
        elif endpoint == "image-editing":
            processes.append('abi:ImageAnalysisProcess')
        elif endpoint == "image-to-video":
            processes.append('abi:VideoGenerationProcess')
        
        return processes
    
    def generate_model_ontology(self, model_data: Dict[str, Any], endpoint: str) -> str:
        """Generate TTL ontology content for a model."""
        model_id = model_data.get('id', '').replace('-', '_')
        model_name = model_data.get('name', 'Unknown Model')
        creator = model_data.get('model_creator', {})
        creator_name = creator.get('name', 'Unknown')
        
        # Determine capabilities and processes
        if endpoint == "llms":
            capabilities = self.map_llm_to_capabilities(model_data)
            processes = self.extract_model_processes_mapping(model_data, endpoint)
        else:
            capabilities = self.map_media_to_capabilities(model_data, endpoint)
            processes = self.extract_model_processes_mapping(model_data, endpoint)
        
        # Build TTL content
        ttl_content = f"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix capability: <http://ontology.naas.ai/abi/capability/> .

# AI Model Instance (Material Entity)
abi:{model_id} a abi:AIModelInstance ;
    rdfs:label "{model_name}"@en ;
    abi:modelName "{model_name}" ;
    abi:providerName "{creator_name}" ;"""

        # Add capabilities - Models HAVE capabilities, not agents
        if capabilities:
            cap_list = ', '.join(capabilities)
            ttl_content += f"""
    abi:hasCapability {cap_list} ;"""

        # Add performance metrics for LLMs
        if endpoint == "llms":
            evaluations = model_data.get('evaluations', {})
            pricing = model_data.get('pricing', {})
            
            ttl_content += f"""
    abi:hasQuality abi:{model_id}_Performance ;"""
            
            if pricing.get('price_1m_input_tokens'):
                ttl_content += f"""
    abi:inputTokenCost "{pricing['price_1m_input_tokens']}"^^xsd:decimal ;"""
            
            if pricing.get('price_1m_output_tokens'):
                ttl_content += f"""
    abi:outputTokenCost "{pricing['price_1m_output_tokens']}"^^xsd:decimal ;"""
            
            if model_data.get('median_output_tokens_per_second'):
                ttl_content += f"""
    abi:outputSpeed "{model_data['median_output_tokens_per_second']}"^^xsd:decimal ;"""
        
            ttl_content += """
     rdfs:comment "AI model instance with benchmarked capabilities and performance data from Artificial Analysis"@en ;
     abi:sourceAPI "https://artificialanalysis.ai/" .

"""
        
        # Add AI processes this model can realize
        if processes:
            ttl_content += """
# AI Processes this model can realize
"""
            for process in processes:
                process_name = process.replace('abi:', '')
                ttl_content += f"""
abi:{model_id}_{process_name}_Realization a {process} ;
    rdfs:label "{model_name} {process_name} Realization"@en ;
    abi:utilizesModel abi:{model_id} ;
    rdfs:comment "Process realization using {model_name} model instance."@en .
"""
        
        # Add performance quality instance for LLMs
        if endpoint == "llms":
            evaluations = model_data.get('evaluations', {})
            ttl_content += f"""# Performance Quality
abi:{model_id}_Performance a abi:ModelAccuracy ;
    rdfs:label "{model_name} Performance"@en ;"""
            
            if evaluations.get('artificial_analysis_intelligence_index'):
                ttl_content += f"""
    abi:intelligenceIndex "{evaluations['artificial_analysis_intelligence_index']}"^^xsd:decimal ;"""
            
            if evaluations.get('artificial_analysis_coding_index'):
                ttl_content += f"""
    abi:codingIndex "{evaluations['artificial_analysis_coding_index']}"^^xsd:decimal ;"""
            
            if evaluations.get('artificial_analysis_math_index'):
                ttl_content += f"""
    abi:mathIndex "{evaluations['artificial_analysis_math_index']}"^^xsd:decimal ;"""
            
            ttl_content += """
     rdfs:comment "Performance metrics from Artificial Analysis benchmarks"@en .

"""
        
        return ttl_content
    
    def to_camel_case(self, model_name: str) -> str:
        """Convert model name to CamelCase following the existing naming convention."""
        # Remove special characters and split by common separators
        import re
        # Replace special characters with spaces
        cleaned = re.sub(r'[^\w\s]', ' ', model_name)
        # Split by spaces and capitalize each word
        words = cleaned.split()
        # Join without spaces, capitalizing each word
        camel_case = ''.join(word.capitalize() for word in words if word)
        # Remove any remaining non-alphanumeric characters
        camel_case = re.sub(r'[^\w]', '', camel_case)
        return camel_case or 'UnknownModel'
    
    def write_individual_model_file(self, module_name: str, filename: str, content: str):
        """Write individual model ontology file to appropriate module directory."""
        module_path = Path(self.config.output_dir) / module_name / "ontologies"
        module_path.mkdir(parents=True, exist_ok=True)
        
        file_path = module_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📝 Generated model ontology: {file_path}")
    
    def write_ontology_file(self, module_name: str, content: str, endpoint: str):
        """Write ontology content to appropriate module directory."""
        module_path = Path(self.config.output_dir) / module_name / "ontologies"
        module_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"AA_{endpoint}_models.ttl"
        file_path = module_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📝 Generated ontology: {file_path}")
    
    def process_artificial_analysis_data(self, params: ArtificialAnalysisParameters) -> Dict[str, Any]:
        """Main processing function for Artificial Analysis data integration."""
        print(f"🚀 Starting Artificial Analysis integration for {params.endpoint}")
        
        # Fetch data from API
        api_data = self.fetch_models_data(params.endpoint, params.include_categories)
        
        if api_data.get('status') == 'error':
            return {"status": "error", "message": "Failed to fetch data from API"}
        
        models = api_data.get('data', [])
        
        # Limit to top 50 models (sorted by intelligence index if available)
        if params.endpoint == "llms":
            models = sorted(models, 
                          key=lambda x: x.get('evaluations', {}).get('artificial_analysis_intelligence_index') or 0, 
                          reverse=True)[:50]
            print("📊 Limited to top 50 models by intelligence index")
        
        results: Dict[str, Any] = {
            "status": "success",
            "endpoint": params.endpoint,
            "models_processed": 0,
            "ontologies_generated": 0,
            "modules": {}
        }
        
        # Group models by provider/module
        module_models: Dict[str, List[Dict[str, Any]]] = {}
        for model in models:
            creator = model.get('model_creator', {})
            module_name = self.determine_model_provider_module(creator)
            
            if module_name not in module_models:
                module_models[module_name] = []
            module_models[module_name].append(model)
        
        # Generate individual ontology files for each model
        if params.generate_ontologies:
            for module_name, module_model_list in module_models.items():
                print(f"🏗️  Processing {len(module_model_list)} models for {module_name}")
                
                # Generate individual TTL file for each model following naming convention
                for model in module_model_list:
                    model_name = model.get('name', 'UnknownModel')
                    
                    # Convert to CamelCase following the pattern: {ModelName}Instances.ttl
                    camel_case_name = self.to_camel_case(model_name)
                    filename = f"{camel_case_name}Instances.ttl"
                    
                    # Generate ontology content for single model
                    model_content = f"""# {model_name} Model Instance
# Generated from: https://artificialanalysis.ai/
# Provider: {model.get('model_creator', {}).get('name', 'Unknown')}
# Generated: {pd.Timestamp.now().isoformat()}

"""
                    model_content += self.generate_model_ontology(model, params.endpoint)
                    
                    # Write individual model ontology file
                    self.write_individual_model_file(module_name, filename, model_content)
                    results["ontologies_generated"] = results["ontologies_generated"] + 1
                
                results["modules"][module_name] = len(module_model_list)
            
            results["models_processed"] = len(models)
        
        print("✅ Completed Artificial Analysis integration:")
        print(f"   - Models processed: {results['models_processed']}")
        print(f"   - Ontologies generated: {results['ontologies_generated']}")
        print(f"   - Modules updated: {list(results['modules'].keys())}")
        
        return results


def create_artificial_analysis_tools(config: ArtificialAnalysisWorkflowConfiguration) -> List[BaseTool]:
    """Create LangChain tools for Artificial Analysis integration."""
    workflow = ArtificialAnalysisWorkflow(config)
    
    def fetch_and_generate_ontologies(
        endpoint: str = "llms",
        include_categories: bool = False,
        generate_ontologies: bool = True
    ) -> str:
        """Fetch AI model data from Artificial Analysis and generate ontology files."""
        params = ArtificialAnalysisParameters(
            endpoint=endpoint,
            include_categories=include_categories,
            generate_ontologies=generate_ontologies
        )
        
        result = workflow.process_artificial_analysis_data(params)
        
        if result["status"] == "success":
            return f"✅ Successfully processed {result['models_processed']} models, generated {result['ontologies_generated']} ontology files for modules: {', '.join(result['modules'].keys())}"
        else:
            return f"❌ Error: {result.get('message', 'Unknown error occurred')}"
    
    return [
        StructuredTool(
            name="artificial_analysis_integration",
            description="Fetch AI model performance data from Artificial Analysis and generate ontology files",
            func=fetch_and_generate_ontologies,
            args_schema=ArtificialAnalysisParameters
        )
    ]



