#!/usr/bin/env python3
"""
ABI System Startup Sequence - Clean linear log flow with timestamps
Shows real system status without fluff
"""

import time
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def check_service(url, name):
    """Check if a service is running"""
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return True
        return False
    except Exception:
        return False

def check_api_key(key_name, key_value=None):
    """Check if an API key is configured"""
    if key_value is None:
        key_value = os.environ.get(key_name)
    
    if not key_value or key_value.strip() == "":
        return False
    
    # Basic validation - check if it looks like a valid API key format
    if len(key_value) < 10:  # Most API keys are longer than 10 chars
        return False
    
    return True



def get_agent_count():
    """Get number of agents from knowledge graph"""
    try:
        query = """
        PREFIX abi: <http://ontology.naas.ai/abi/>
        SELECT (COUNT(*) AS ?count) WHERE {
            ?s a abi:AIAgent .
        }
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Agent count query failed: {str(e)}")

def get_agent_breakdown():
    """Get actual agent breakdown from knowledge graph"""
    try:
        query = """
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?system ?systemLabel (COUNT(?agent) AS ?count) WHERE {
            ?agent a abi:AIAgent .
            ?agent abi:isAIAgentOf ?system .
            OPTIONAL { ?system rdfs:label ?systemLabel }
        }
        GROUP BY ?system ?systemLabel
        ORDER BY ?systemLabel
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            agent_groups = {}
            
            for binding in result['results']['bindings']:
                system_uri = binding['system']['value']
                system_label = binding.get('systemLabel', {}).get('value', 'Unknown')
                count = int(binding['count']['value'])
                
                # Extract clean system name from URI or label
                if system_label and system_label != 'Unknown':
                    system_name = system_label
                else:
                    # Extract from URI as fallback
                    system_name = system_uri.split('/')[-1]
                    # Clean up the name
                    system_name = system_name.replace('System', '').replace('Subsystem', '')
                
                # Group by main AI provider for cleaner display
                main_provider = get_main_provider(system_uri, system_name)
                
                if main_provider not in agent_groups:
                    agent_groups[main_provider] = 0
                agent_groups[main_provider] += count
            
            return agent_groups
        return {}
    except Exception:
        return {}

def get_main_provider(system_uri, system_name):
    """Extract main AI provider from system URI or name"""
    uri_lower = system_uri.lower()
    
    # Map to main providers
    if 'openai' in uri_lower or 'chatgpt' in uri_lower:
        return "OpenAI"
    elif 'anthropic' in uri_lower or 'claude' in uri_lower:
        return "Anthropic"
    elif 'google' in uri_lower or 'gemini' in uri_lower:
        return "Google"
    elif 'mistral' in uri_lower:
        return "Mistral"
    elif 'grok' in uri_lower or 'xai' in uri_lower:
        return "XAI (Grok)"
    elif 'llama' in uri_lower:
        return "Llama"
    elif 'deepseek' in uri_lower:
        return "DeepSeek"
    elif 'gemma' in uri_lower:
        return "Gemma"
    elif 'qwen' in uri_lower:
        return "Qwen"
    elif 'perplexity' in uri_lower:
        return "Perplexity"
    elif 'abi' in uri_lower:
        return "ABI Core"
    else:
        return system_name

def get_triple_count():
    """Get total triple count"""
    try:
        query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Triple count query failed: {str(e)}")

def get_type_statement_count():
    """Get number of type statements"""
    try:
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT (COUNT(*) AS ?count) WHERE {
            ?s a ?o .
        }
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Type statement count query failed: {str(e)}")

def get_class_count():
    """Get number of classes"""
    try:
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?class) AS ?count) WHERE {
            ?class a ?type .
            FILTER(?type IN (rdfs:Class, owl:Class))
        }
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Class count query failed: {str(e)}")

def get_data_property_count():
    """Get number of data properties"""
    try:
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?prop) AS ?count) WHERE {
            ?prop a owl:DatatypeProperty .
        }
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Data properties query failed: {str(e)}")

def get_object_property_count():
    """Get number of object properties"""
    try:
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?prop) AS ?count) WHERE {
            ?prop a owl:ObjectProperty .
        }
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Object property count query failed: {str(e)}")

def get_instance_count():
    """Get number of instances"""
    try:
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT (COUNT(DISTINCT ?instance) AS ?count) WHERE {
            ?instance a ?class .
            ?class a rdfs:Class .
        }
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return int(result['results']['bindings'][0]['count']['value'])
        raise Exception(f"SPARQL query failed with status {response.status_code}")
    except Exception as e:
        raise Exception(f"Instance count query failed: {str(e)}")

def run_startup_sequence():
    """Run clean startup sequence with timestamps"""
    start_time = time.time()
    
    def log(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        elapsed = f"{(time.time() - start_time)*1000:.0f}ms"
        print(f"[{timestamp}] {elapsed:>6} {message}")
    
    log("🧠 ABI System Starting up...")
    log("=" * 50)
    
    # Step 1: Check if services are available
    log("[1/4] Checking services...")
    oxigraph_ok = check_service("http://localhost:7878", "Oxigraph")
    log(f"{'✅' if oxigraph_ok else '❌'} Oxigraph")
    
    yasgui_ok = check_service("http://localhost:3000", "YasGUI")
    log(f"{'✅' if yasgui_ok else '❌'} YasGUI")
    
    ollama_ok = check_service("http://localhost:11434/api/tags", "Ollama")
    log(f"{'✅' if ollama_ok else '❌'} Ollama")
    
    # Check API keys for AI providers
    log("🔑 Checking API keys...")
    
    openai_ok = check_api_key("OPENAI_API_KEY")
    log(f"{'✅' if openai_ok else '❌'} OpenAI API Key")
    
    anthropic_ok = check_api_key("ANTHROPIC_API_KEY")
    log(f"{'✅' if anthropic_ok else '❌'} Anthropic API Key")
    
    google_ok = check_api_key("GOOGLE_API_KEY")
    log(f"{'✅' if google_ok else '❌'} Google API Key")
    
    perplexity_ok = check_api_key("PERPLEXITY_API_KEY")
    log(f"{'✅' if perplexity_ok else '❌'} Perplexity API Key")
    
    mistral_ok = check_api_key("MISTRAL_API_KEY")
    log(f"{'✅' if mistral_ok else '❌'} Mistral API Key")
    
    xai_ok = check_api_key("XAI_API_KEY")
    log(f"{'✅' if xai_ok else '❌'} XAI API Key (Grok)")
    
    # Step 2: Load knowledge graph data (only if Oxigraph is available)
    log("[2/4] Loading knowledge graph...")
    if oxigraph_ok:
        # Check each query individually with proper error handling
        agent_count_ok = True
        try:
            agent_count = get_agent_count()
            log(f"ℹ️ AI Agents: {agent_count}")
        except Exception:
            log("❌ AI Agents: Query failed")
            agent_count_ok = False
        
        triple_count_ok = True
        try:
            triple_count = get_triple_count()
            log(f"ℹ️ Total Triples: {triple_count:,}")
        except Exception:
            log("❌ Total Triples: Query failed")
            triple_count_ok = False
        
        type_statements_ok = True
        try:
            type_statements = get_type_statement_count()
            log(f"ℹ️ Type Statements: {type_statements:,}")
        except Exception:
            log("❌ Type Statements: Query failed")
            type_statements_ok = False
        
        class_count_ok = True
        try:
            class_count = get_class_count()
            log(f"ℹ️ Classes: {class_count:,}")
        except Exception:
            log("❌ Classes: Query failed")
            class_count_ok = False
        
        data_property_count_ok = True
        try:
            data_property_count = get_data_property_count()
            log(f"ℹ️ Data Properties: {data_property_count:,}")
        except Exception:
            log("❌ Data Properties: Query failed")
            data_property_count_ok = False
        
        object_property_count_ok = True
        try:
            object_property_count = get_object_property_count()
            log(f"ℹ️ Object Properties: {object_property_count:,}")
        except Exception:
            log("❌ Object Properties: Query failed")
            object_property_count_ok = False
        
        instance_count_ok = True
        try:
            instance_count = get_instance_count()
            log(f"ℹ️ Instances: {instance_count:,}")
        except Exception:
            log("❌ Instances: Query failed")
            instance_count_ok = False
        
        # Step 3: Show actual agent breakdown from data
        log("[3/4] Agent breakdown:")
        agent_groups = get_agent_breakdown()
        if agent_groups:
            for group, count in sorted(agent_groups.items()):
                log(f"✅ {group}: {count} agents")
        else:
            log("⚠️  No agents found in knowledge graph")
    else:
        log("❌ Cannot load knowledge graph - Oxigraph not available")
        # Initialize variables to avoid NameError
        agent_count_ok = False
        triple_count_ok = False
        type_statements_ok = False
        class_count_ok = False
        data_property_count_ok = False
        object_property_count_ok = False
        instance_count_ok = False
        # Initialize API key variables
        openai_ok = check_api_key("OPENAI_API_KEY")
        anthropic_ok = check_api_key("ANTHROPIC_API_KEY")
        google_ok = check_api_key("GOOGLE_API_KEY")
        perplexity_ok = check_api_key("PERPLEXITY_API_KEY")
        mistral_ok = check_api_key("MISTRAL_API_KEY")
        xai_ok = check_api_key("XAI_API_KEY")
    
    # Step 4: Final status and access URLs
    log("[4/4] System status:")
    if oxigraph_ok and yasgui_ok and ollama_ok:
        log("✅ All services running")
        
        # Check knowledge graph query status
        kg_queries_ok = all([
            agent_count_ok, triple_count_ok, type_statements_ok,
            class_count_ok, data_property_count_ok, 
            object_property_count_ok, instance_count_ok
        ])
        
        if kg_queries_ok:
            log("✅ Knowledge graph loaded")
        else:
            log("⚠️  Knowledge graph partially loaded (some queries failed)")
        
        # Check API key status
        api_keys_configured = sum([openai_ok, anthropic_ok, google_ok, perplexity_ok, mistral_ok, xai_ok])
        total_api_keys = 6
        
        if api_keys_configured == 0:
            log("❌ No API keys configured")
        elif api_keys_configured == total_api_keys:
            log("✅ All API keys configured")
        else:
            log(f"⚠️  {api_keys_configured}/{total_api_keys} API keys configured")
        
        log("✅ Local models available")
        log("🌐 SPARQL: http://localhost:3000")
        log("🔍 Explorer: http://localhost:7878/")
        log("🤖 Ollama: http://localhost:11434")
    else:
        log("⚠️  Some services not available")
        if not oxigraph_ok:
            log("❌ Run: make dev-up")
        if not ollama_ok:
            log("❌ Run: ollama serve")
    
    log("🚀 Ready")

def main():
    run_startup_sequence()

if __name__ == "__main__":
    main()
