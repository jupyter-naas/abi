#!/usr/bin/env python3
"""
Generate AI Agent Ontologies from Artificial Analysis Data

This script processes the Artificial Analysis data and creates proper BFO-compliant
ontologies for each AI agent (ChatGPT, Claude, etc.) with their associated models,
evaluations, and BFO 7-bucket elements.

Usage:
    python scripts/generate_ai_agent_ontologies.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import urllib.parse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def load_artificial_analysis_data() -> Dict[str, Any]:
    """Load the latest Artificial Analysis data from storage."""
    storage_dir = Path("storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow")
    
    if not storage_dir.exists():
        raise FileNotFoundError(f"Storage directory not found: {storage_dir}")
    
    # Get the latest JSON file
    json_files = list(storage_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {storage_dir}")
    
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"📂 Loading data from: {latest_file}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def determine_ai_agent_module(model_creator: Dict[str, Any]) -> Optional[str]:
    """Map model creator to AI agent module name."""
    creator_name = model_creator.get('name', '').lower()
    creator_slug = model_creator.get('slug', '').lower()
    
    # Provider to module mapping
    provider_mapping = {
        'openai': 'chatgpt',
        'anthropic': 'claude',
        'google': 'gemini', 
        'x.ai': 'grok',
        'xai': 'grok',
        'mistral ai': 'mistral',
        'mistral': 'mistral',
        'meta': 'llama',
        'deepseek': 'deepseek',
        'perplexity': 'perplexity',
        'alibaba': 'qwen'
    }
    
    # Try exact match first
    if creator_name in provider_mapping:
        return provider_mapping[creator_name]
    
    if creator_slug in provider_mapping:
        return provider_mapping[creator_slug]
    
    # Try partial matches
    for key, module in provider_mapping.items():
        if key in creator_name or key in creator_slug:
            return module
    
    return None

def generate_uri_safe_id(text: str) -> str:
    """Generate URI-safe identifier from text."""
    # Replace spaces and special characters with underscores
    safe_id = text.replace(' ', '_').replace('-', '_').replace('.', '_')
    # Remove parentheses and other special chars
    safe_id = ''.join(c for c in safe_id if c.isalnum() or c == '_')
    # Remove multiple underscores
    while '__' in safe_id:
        safe_id = safe_id.replace('__', '_')
    return safe_id.strip('_')

def format_release_date(date_str: str) -> str:
    """Format release date for BFO temporal entity."""
    try:
        # Parse the date and format as ISO
        if date_str:
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return parsed_date.strftime('%Y-%m-%d')
    except:
        pass
    return "unknown"

def generate_model_ontology(model_data: Dict[str, Any], agent_module: str) -> str:
    """Generate TTL ontology for a single AI model."""
    
    # Extract basic model info
    model_id = model_data.get('id', '')
    model_name = model_data.get('name', 'Unknown Model')
    model_slug = model_data.get('slug', '')
    release_date = model_data.get('release_date', '')
    
    # Model creator info
    creator = model_data.get('model_creator', {})
    creator_name = creator.get('name', 'Unknown')
    creator_slug = creator.get('slug', 'unknown')
    
    # Generate safe URIs
    model_uri_id = generate_uri_safe_id(model_slug or model_id)
    creator_uri_id = generate_uri_safe_id(creator_slug)
    
    # Format dates
    formatted_release_date = format_release_date(release_date)
    current_time = datetime.now(timezone.utc).isoformat()
    
    ttl_content = f'''
# {model_name} - AI Model Instance
# Generated: {current_time}
# Source: Artificial Analysis API

# AI Model Instance (Material Entity - BFO_0000040)
abi:{model_uri_id} a abi:AIModelInstance ;
    rdfs:label "{model_name}"@en ;
    abi:modelName "{model_name}" ;
    abi:modelSlug "{model_slug}" ;
    abi:artificialAnalysisId "{model_id}" ;
    abi:providerName "{creator_name}" ;
    abi:belongsToAgent abi:{agent_module.title()}Agent ;
    bfo:participates_in abi:{model_uri_id}_ProcessRealization ;
    bfo:has_quality abi:{model_uri_id}_Performance ;
    bfo:located_in abi:{creator_uri_id}_InfrastructureSite ;
    bfo:exists_at abi:{model_uri_id}_ReleaseTemporalRegion ;
    rdfs:comment "AI model instance with benchmarked capabilities and performance data"@en .

# AI Agent (this model belongs to)
abi:{agent_module.title()}Agent a abi:AIAgent ;
    rdfs:label "{agent_module.title()} AI Agent"@en ;
    abi:utilizesModel abi:{model_uri_id} ;
    rdfs:comment "AI Agent that can utilize the {model_name} model"@en .

# Provider/Creator Entity (Independent Continuant - BFO_0000004)  
abi:{creator_uri_id}_Organization a bfo:BFO_0000027 ;  # object aggregate
    rdfs:label "{creator_name}"@en ;
    abi:organizationName "{creator_name}" ;
    abi:organizationSlug "{creator_slug}" ;
    bfo:has_part abi:{creator_uri_id}_InfrastructureSite ;
    rdfs:comment "Organization that created and operates the {model_name} model"@en .

# Infrastructure Site (Site - BFO_0000029)
abi:{creator_uri_id}_InfrastructureSite a bfo:BFO_0000029 ;
    rdfs:label "{creator_name} Infrastructure Site"@en ;
    bfo:part_of abi:{creator_uri_id}_Organization ;
    rdfs:comment "Physical/virtual infrastructure site where {model_name} operates"@en .

# Release Temporal Region (Temporal Region - BFO_0000008)
abi:{model_uri_id}_ReleaseTemporalRegion a bfo:BFO_0000008 ;
    rdfs:label "{model_name} Release Date"@en ;
    abi:releaseDate "{formatted_release_date}"^^xsd:date ;
    abi:releaseDateRaw "{release_date}" ;
    rdfs:comment "Temporal region marking the release of {model_name}"@en .'''

    # Add pricing information (Qualities - BFO_0000019)
    pricing = model_data.get('pricing', {})
    if pricing:
        ttl_content += f'''

# Pricing Quality (Quality - BFO_0000019)
abi:{model_uri_id}_PricingQuality a bfo:BFO_0000019 ;
    rdfs:label "{model_name} Pricing Information"@en ;
    bfo:inheres_in abi:{model_uri_id} ;'''
        
        if pricing.get('price_1m_input_tokens'):
            ttl_content += f'''
    abi:inputTokenCost "{pricing['price_1m_input_tokens']}"^^xsd:decimal ;'''
        
        if pricing.get('price_1m_output_tokens'):
            ttl_content += f'''
    abi:outputTokenCost "{pricing['price_1m_output_tokens']}"^^xsd:decimal ;'''
        
        if pricing.get('price_1m_blended_3_to_1'):
            ttl_content += f'''
    abi:blendedCost "{pricing['price_1m_blended_3_to_1']}"^^xsd:decimal ;'''
        
        ttl_content += f'''
    rdfs:comment "Pricing information for {model_name} per million tokens"@en .'''

    # Add performance metrics (Qualities - BFO_0000019)
    if model_data.get('median_output_tokens_per_second') or model_data.get('median_time_to_first_token_seconds'):
        ttl_content += f'''

# Performance Quality (Quality - BFO_0000019)
abi:{model_uri_id}_PerformanceQuality a bfo:BFO_0000019 ;
    rdfs:label "{model_name} Performance Metrics"@en ;
    bfo:inheres_in abi:{model_uri_id} ;'''
        
        if model_data.get('median_output_tokens_per_second'):
            ttl_content += f'''
    abi:outputSpeed "{model_data['median_output_tokens_per_second']}"^^xsd:decimal ;'''
        
        if model_data.get('median_time_to_first_token_seconds'):
            ttl_content += f'''
    abi:timeToFirstToken "{model_data['median_time_to_first_token_seconds']}"^^xsd:decimal ;'''
        
        if model_data.get('median_time_to_first_answer_token'):
            ttl_content += f'''
    abi:timeToFirstAnswerToken "{model_data['median_time_to_first_answer_token']}"^^xsd:decimal ;'''
        
        ttl_content += f'''
    rdfs:comment "Performance metrics for {model_name} from Artificial Analysis benchmarks"@en .'''

    # Add evaluation metrics (Qualities - BFO_0000019) 
    evaluations = model_data.get('evaluations', {})
    if evaluations:
        ttl_content += f'''

# Evaluation Quality (Quality - BFO_0000019)
abi:{model_uri_id}_EvaluationQuality a bfo:BFO_0000019 ;
    rdfs:label "{model_name} Evaluation Scores"@en ;
    bfo:inheres_in abi:{model_uri_id} ;'''
        
        # Add each evaluation metric as a property
        for eval_name, eval_value in evaluations.items():
            if eval_value is not None:
                safe_eval_name = generate_uri_safe_id(eval_name)
                ttl_content += f'''
    abi:{safe_eval_name} "{eval_value}"^^xsd:decimal ;'''
        
        ttl_content += f'''
    abi:sourceAPI "https://artificialanalysis.ai/" ;
    rdfs:comment "Evaluation scores for {model_name} from various benchmarks"@en .'''

    # Add Process Realization (Process - BFO_0000015)
    ttl_content += f'''

# Model Process Realization (Process - BFO_0000015)
abi:{model_uri_id}_ProcessRealization a bfo:BFO_0000015 ;
    rdfs:label "{model_name} Inference Process"@en ;
    bfo:has_participant abi:{model_uri_id} ;
    bfo:occurs_in abi:{creator_uri_id}_InfrastructureSite ;
    bfo:occupies_temporal_region abi:{model_uri_id}_ReleaseTemporalRegion ;
    rdfs:comment "Process of model inference and text generation by {model_name}"@en .

# Performance Quality Collection (inheres in the model)
abi:{model_uri_id}_Performance a bfo:BFO_0000019 ;
    rdfs:label "{model_name} Overall Performance"@en ;
    bfo:inheres_in abi:{model_uri_id} ;
    bfo:has_part abi:{model_uri_id}_PricingQuality ;'''
    
    if model_data.get('median_output_tokens_per_second') or model_data.get('median_time_to_first_token_seconds'):
        ttl_content += f'''
    bfo:has_part abi:{model_uri_id}_PerformanceQuality ;'''
    
    if evaluations:
        ttl_content += f'''
    bfo:has_part abi:{model_uri_id}_EvaluationQuality ;'''
    
    ttl_content += f'''
    rdfs:comment "Overall performance characteristics of {model_name}"@en .

'''
    
    return ttl_content

def generate_agent_ontology_file(agent_module: str, models: List[Dict[str, Any]]) -> str:
    """Generate complete ontology file for an AI agent and its models."""
    
    current_time = datetime.now(timezone.utc).isoformat()
    agent_title = agent_module.title()
    
    # TTL header with all necessary prefixes
    header = f'''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix abi: <http://ontology.naas.ai/abi/> .

# {agent_title} Agent Model Ontology
# Generated from Artificial Analysis API data
# Generated: {current_time}
# Total Models: {len(models)}

<http://ontology.naas.ai/abi/{agent_module}> a owl:Ontology ;
    rdfs:label "{agent_title} Agent Model Ontology"@en ;
    rdfs:comment "Ontology defining {agent_title} AI agent and its associated models with BFO-compliant structure"@en ;
    owl:versionInfo "1.0" ;
    abi:generatedFrom "https://artificialanalysis.ai/" ;
    abi:generatedAt "{current_time}"^^xsd:dateTime .

'''
    
    # Generate ontology content for each model
    content = header
    for model in models:
        content += generate_model_ontology(model, agent_module)
    
    return content

def main():
    """Main function to generate AI agent ontologies."""
    print("🚀 Starting AI Agent Ontology Generation")
    
    # Load Artificial Analysis data
    try:
        aa_data = load_artificial_analysis_data()
        models = aa_data.get('data', [])
        print(f"📊 Loaded {len(models)} models from Artificial Analysis")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return False
    
    # Group models by AI agent module
    agent_models = {}
    unassigned_models = []
    
    for model in models:
        creator = model.get('model_creator', {})
        agent_module = determine_ai_agent_module(creator)
        
        if agent_module:
            if agent_module not in agent_models:
                agent_models[agent_module] = []
            agent_models[agent_module].append(model)
        else:
            unassigned_models.append(model)
    
    print(f"📋 Grouped models into {len(agent_models)} AI agents")
    if unassigned_models:
        print(f"⚠️  {len(unassigned_models)} models could not be assigned to agents")
    
    # Generate ontology files for each agent
    output_dir = Path("storage/datastore/core/modules/ai_agent_ontologies")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_files = []
    
    for agent_module, models in agent_models.items():
        print(f"🏗️  Generating ontology for {agent_module} ({len(models)} models)")
        
        # Generate ontology content
        ontology_content = generate_agent_ontology_file(agent_module, models)
        
        # Write to file
        filename = f"{agent_module}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.ttl"
        output_file = output_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(ontology_content)
        
        generated_files.append(output_file)
        print(f"📝 Generated: {output_file}")
    
    # Generate summary report
    summary_file = output_dir / f"generation_summary_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_models_processed": len(models),
        "agents_generated": len(agent_models),
        "unassigned_models": len(unassigned_models),
        "agent_breakdown": {agent: len(models) for agent, models in agent_models.items()},
        "generated_files": [str(f) for f in generated_files],
        "unassigned_creators": [model.get('model_creator', {}).get('name', 'Unknown') 
                               for model in unassigned_models]
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Generation Complete!")
    print(f"📊 Summary:")
    print(f"   - {len(generated_files)} ontology files generated")
    print(f"   - {len(models)} total models processed")
    print(f"   - {len(agent_models)} AI agents covered")
    print(f"📁 Output directory: {output_dir}")
    print(f"📋 Summary report: {summary_file}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
