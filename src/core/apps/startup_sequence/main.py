#!/usr/bin/env python3
"""
ABI System Startup Sequence - Clean linear log flow with timestamps
Shows real system status without fluff
"""

import time
import requests
from datetime import datetime

def check_service(url, name):
    """Check if a service is running"""
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return True
        return False
    except Exception:
        return False



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
        return 0
    except Exception:
        return 0

def get_agent_breakdown():
    """Get actual agent breakdown from knowledge graph"""
    try:
        query = """
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?label WHERE {
            ?s a abi:AIAgent .
            ?s rdfs:label ?label .
        }
        ORDER BY ?label
        """
        response = requests.post(
            "http://localhost:7878/query",
            data=query,
            headers={'Content-Type': 'application/sparql-query'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            agents = [binding['label']['value'] for binding in result['results']['bindings']]
            
            # Group agents by main type for cleaner display
            agent_groups = {}
            for agent in agents:
                if "ABI" in agent:
                    group = "ABI Core"
                elif "ChatGPT" in agent or "GPT" in agent:
                    group = "ChatGPT"
                elif "Claude" in agent:
                    group = "Claude"
                elif "Gemini" in agent:
                    group = "Gemini"
                elif "Mistral" in agent:
                    group = "Mistral"
                elif "Grok" in agent:
                    group = "Grok"
                elif "Llama" in agent:
                    group = "Llama"
                elif "DeepSeek" in agent:
                    group = "DeepSeek"
                elif "Gemma" in agent:
                    group = "Gemma"
                elif "Qwen" in agent:
                    group = "Qwen"
                elif "Perplexity" in agent:
                    group = "Perplexity"
                elif "DALL-E" in agent:
                    group = "DALL-E"
                else:
                    group = "Other"
                
                if group not in agent_groups:
                    agent_groups[group] = 0
                agent_groups[group] += 1
            
            return agent_groups
        return {}
    except Exception:
        return {}

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
        return 0
    except Exception:
        return 0

def get_class_count():
    """Get number of classes"""
    try:
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT (COUNT(DISTINCT ?class) AS ?count) WHERE {
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
        return 0
    except Exception:
        return 0

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
        return 0
    except Exception:
        return 0

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
        return 0
    except Exception:
        return 0

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
        return 0
    except Exception:
        return 0

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
    
    # Step 2: Load knowledge graph data (only if Oxigraph is available)
    log("[2/4] Loading knowledge graph...")
    if oxigraph_ok:
        agent_count = get_agent_count()
        log(f"ℹ️ AI Agents: {agent_count}")
        
        triple_count = get_triple_count()
        log(f"ℹ️ Total Triples: {triple_count:,}")
        
        class_count = get_class_count()
        log(f"ℹ️ Classes: {class_count:,}")
        
        data_property_count = get_data_property_count()
        log(f"ℹ️ Data Properties: {data_property_count:,}")
        
        object_property_count = get_object_property_count()
        log(f"ℹ️ Object Properties / Relations: {object_property_count:,}")
        
        instance_count = get_instance_count()
        log(f"ℹ️ Instances: {instance_count:,}")
        
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
        agent_count = 0
        triple_count = 0
    
    # Step 4: Final status and access URLs
    log("[4/4] System status:")
    if oxigraph_ok and yasgui_ok and ollama_ok:
        log("✅ All services running")
        log("✅ Knowledge graph loaded")
        log("✅ Local models available")
        log("")
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
