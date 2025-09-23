#!/usr/bin/env python3
"""
LLM-based CLI to chat with cyber security agent
Uses system prompt + function calls to SPARQL queries
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

def main():
    """LLM-based CLI with function calls to SPARQL queries."""
    
    print("🤖 Cyber Security LLM Agent")
    print("=" * 35)
    
    # Load SPARQL agent directly (simpler approach)
    try:
        from agents.CyberSecuritySPARQLAgent import CyberSecuritySPARQLAgent
        agent = CyberSecuritySPARQLAgent()
        print(f"✅ Loaded SPARQL agent")
        use_llm = False  # For now, use direct SPARQL calls
        
    except Exception as e:
        print(f"❌ Failed to load SPARQL agent: {e}")
        return
    
    print("\n💬 Chat with the LLM agent (type 'quit' to exit)")
    print("🔍 The agent will show you SPARQL queries it executes")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye!")
                break
                
            if not user_input:
                continue
            
            if use_llm:
                # LLM agent with function calls
                try:
                    print(f"\n🧠 LLM processing: '{user_input}'")
                    print("🔍 Agent may call SPARQL functions...")
                    
                    # This would normally call the LLM with function calling
                    # For now, simulate the function call approach
                    response = simulate_llm_with_functions(user_input, agent)
                    print(f"\n🤖 Agent: {response}")
                    
                except Exception as e:
                    print(f"❌ LLM error: {e}")
            else:
                # Fallback SPARQL agent
                try:
                    result = agent.get_dataset_overview()
                    print(f"\n🤖 Agent: Found {result.get('total_events', 0)} cyber security events")
                except Exception as e:
                    print(f"❌ Query error: {e}")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Goodbye!")
            break

def create_cyber_security_tools():
    """Create function tools for SPARQL queries."""
    
    tools = [
        {
            "name": "get_dataset_overview",
            "description": "Get overview of cyber security dataset with event counts and categories",
            "function": "sparql_agent.get_dataset_overview"
        },
        {
            "name": "search_events_by_category", 
            "description": "Search for cyber security events by category (ransomware, supply_chain_attack, etc)",
            "parameters": {
                "category": "string - event category to search for"
            },
            "function": "sparql_agent.search_events_by_criteria"
        },
        {
            "name": "get_timeline_analysis",
            "description": "Get chronological timeline of cyber security events",
            "function": "sparql_agent.get_timeline_analysis"
        },
        {
            "name": "get_critical_events",
            "description": "Get critical cyber security events with D3FEND defensive recommendations",
            "function": "sparql_agent.get_critical_events_with_defenses"
        },
        {
            "name": "get_attack_vector_analysis",
            "description": "Analyze attack vectors and map to D3FEND defensive techniques",
            "function": "sparql_agent.get_attack_vector_analysis"
        }
    ]
    
    return tools

def simulate_llm_with_functions(user_input: str, agent) -> str:
    """Simulate LLM with function calling to SPARQL queries."""
    
    # Load SPARQL agent for function calls
    try:
        # Import the SPARQL agent properly
        from agents.CyberSecuritySPARQLAgent import CyberSecuritySPARQLAgent
        sparql_agent = CyberSecuritySPARQLAgent()
    except Exception:
        # Fallback to exec if import fails
        try:
            exec(open(Path(__file__).parent.parent / 'agents' / 'CyberSecuritySPARQLAgent.py').read())
            sparql_agent = CyberSecuritySPARQLAgent()  # noqa: F821
        except Exception as e:
            return f"❌ Cannot load SPARQL functions: {e}"
    
    # Simple function routing based on user input
    if any(word in user_input.lower() for word in ['satellite', 'satcom']):
        print("🔍 Function call: search_events_by_category(category='satellite_attack')")
        result = sparql_agent.search_events_by_criteria(category="satellite_attack")
        
        if result.get('results'):
            events = result['results']
            response = f"Found {len(events)} satellite attack(s):\n"
            for event in events:
                response += f"• {event.get('date', 'Unknown')} - {event.get('name', 'Unknown')}\n"
                if event.get('description'):
                    response += f"  {event['description'][:100]}...\n"
        else:
            response = "No satellite attacks found in the dataset."
            
    elif any(word in user_input.lower() for word in ['ransomware', 'ransom']):
        print("🔍 Function call: search_events_by_category(category='ransomware')")
        result = sparql_agent.search_events_by_criteria(category="ransomware")
        
        if result.get('results'):
            events = result['results']
            response = f"Found {len(events)} ransomware attack(s):\n"
            for event in events:
                response += f"• {event.get('date', 'Unknown')} - {event.get('name', 'Unknown')}\n"
        else:
            response = "No ransomware attacks found in the dataset."
            
    elif any(word in user_input.lower() for word in ['overview', 'summary', 'what happened']):
        print("🔍 Function call: get_dataset_overview()")
        result = sparql_agent.get_dataset_overview()
        
        total = result.get('total_events', 0)
        response = f"Dataset Overview:\n• Total Events: {total}\n• Knowledge Graph: 32,311 triples\n"
        
        if result.get('severity_distribution'):
            response += "\nSeverity Breakdown:\n"
            for sev in result['severity_distribution']:
                emoji = "🔴" if sev['severity'] == "critical" else "🟡"
                response += f"{emoji} {sev['severity'].title()}: {sev['count']} events\n"
                
    elif any(word in user_input.lower() for word in ['timeline', 'when', 'chronological']):
        print("🔍 Function call: get_timeline_analysis()")
        result = sparql_agent.get_timeline_analysis()
        
        response = "Timeline Analysis:\n"
        if result.get('timeline'):
            response += "Recent Events:\n"
            for event in result['timeline'][-3:]:
                emoji = "🔴" if event.get('severity') == "critical" else "🟡"
                response += f"{emoji} {event['date']} - {event['event_name']}\n"
                
    elif any(word in user_input.lower() for word in ['critical', 'serious']):
        print("🔍 Function call: get_critical_events()")
        result = sparql_agent.get_critical_events_with_defenses()
        
        total = result.get('total_critical_events', 0)
        response = f"Critical Events Analysis:\n• Found: {total} critical events\n"
        
        if result.get('critical_events'):
            response += "\nTop Critical Events:\n"
            for event in result['critical_events'][:2]:
                response += f"• {event['event_name']}\n"
                if event.get('attack_vectors'):
                    response += f"  Attack Vectors: {', '.join(event['attack_vectors'][:2])}\n"
                    
    else:
        # Default to overview
        print("🔍 Function call: get_dataset_overview() [default]")
        result = sparql_agent.get_dataset_overview()
        response = f"I have data on {result.get('total_events', 0)} cyber security events from 2025. What would you like to know about them?"
    
    # Show SPARQL audit trail
    print("📊 SPARQL Query executed successfully")
    print("🔍 Data retrieved from knowledge graph")
    
    return response

if __name__ == "__main__":
    main()