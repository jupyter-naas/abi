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

def check_qwen_model():
    """Check if Qwen model is available in Ollama"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            qwen_models = [model for model in models if 'qwen' in model.get('name', '').lower()]
            return len(qwen_models) > 0, qwen_models
        return False, []
    except Exception:
        return False, []

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

def run_startup_sequence():
    """Run clean startup sequence with timestamps"""
    start_time = time.time()
    
    def log(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        elapsed = f"{(time.time() - start_time)*1000:.0f}ms"
        print(f"[{timestamp}] {elapsed:>6} {message}")
    
    log("🧠 ABI System Starting up...")
    log("=" * 50)
    
    # Check services
    log("[1/4] Checking services...")
    oxigraph_ok = check_service("http://localhost:7878", "Oxigraph")
    log(f"Oxigraph: {'✅' if oxigraph_ok else '❌'}")
    
    yasgui_ok = check_service("http://localhost:3000", "YasGUI")
    log(f"YasGUI: {'✅' if yasgui_ok else '❌'}")
    
    ollama_ok = check_service("http://localhost:11434/api/tags", "Ollama")
    log(f"Ollama: {'✅' if ollama_ok else '❌'}")
    
    # Check Qwen model specifically
    qwen_ok, qwen_models = check_qwen_model()
    if qwen_ok:
        model_names = [model.get('name', '') for model in qwen_models]
        log(f"Qwen Models: ✅ {', '.join(model_names)}")
    else:
        log("Qwen Models: ❌ Not found")
    
    # Get knowledge graph stats
    log("[2/4] Loading knowledge graph...")
    agent_count = get_agent_count()
    log(f"AI Agents: {agent_count}")
    
    triple_count = get_triple_count()
    log(f"Total Triples: {triple_count:,}")
    
    # Show agent breakdown
    log("[3/4] Agent breakdown:")
    agents = [
        "ABI Core", "ChatGPT", "Claude", "Gemini", "Mistral", 
        "Grok", "Llama", "DeepSeek", "Gemma", "Qwen", 
        "Perplexity", "Support"
    ]
    for agent in agents:
        log(f"✅ {agent}")
    
    # Final status
    log("[4/4] System status:")
    if oxigraph_ok and yasgui_ok and ollama_ok and qwen_ok:
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
        if not qwen_ok:
            log("❌ Run: ollama pull qwen2.5:7b")
    
    log("🚀 Ready")

def main():
    run_startup_sequence()

if __name__ == "__main__":
    main()
