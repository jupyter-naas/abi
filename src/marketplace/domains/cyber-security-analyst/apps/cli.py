#!/usr/bin/env python3
"""
Cyber Security Agent CLI - Proper ABI IntentAgent with SPARQL function calls
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

def main():
    """Main CLI using proper ABI IntentAgent with function calls."""
    
    print("🤖 Cyber Security Agent (ABI IntentAgent)")
    print("=" * 45)
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  OPENAI_API_KEY not set")
        print("💡 Set your API key to enable full LLM conversation:")
        print("   export OPENAI_API_KEY='your-key-here'")
        print("\n🔄 Using fallback conversational mode...")
        use_fallback = True
    else:
        use_fallback = False
    
    if not use_fallback:
        # Try to use the real CyberSecurityAnalystAgent
        try:
            from agents.CyberSecurityAnalystAgent import create_agent
            agent = create_agent()
            print(f"✅ Loaded {agent.name} (ABI Agent)")
            print(f"🧠 LLM-powered with SPARQL function calls")
            
            print("\n💬 Chat with the agent (type 'quit' to exit)")
            print("🔍 The agent will call SPARQL functions as needed")
            print("-" * 50)
            
            while True:
                try:
                    user_input = input(f"\n💬 You: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print(f"\n👋 Au revoir!")
                        break
                        
                    if not user_input:
                        continue
                    
                    # Use the agent's invoke method (ABI pattern)
                    print(f"\n🧠 {agent.name} processing...")
                    response = agent.invoke(user_input)
                    print(f"\n🤖 {agent.name}: {response}")
                        
                except KeyboardInterrupt:
                    print(f"\n\n👋 Au revoir!")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    
        except Exception as e:
            print(f"❌ Failed to load ABI agent: {e}")
            use_fallback = True
    
    if use_fallback:
        # Fallback conversational mode
        print("✅ Loaded CyberSec (Fallback Mode)")
        print("🧠 Natural conversation with SPARQL backend")
        
        # Load SPARQL agent for queries
        try:
            exec(open(module_dir / 'agents' / 'CyberSecuritySPARQLAgent.py').read())
            sparql_agent = CyberSecuritySPARQLAgent()  # noqa: F821
            has_knowledge_graph = sparql_agent.graph is not None
            print(f"✅ Knowledge graph: {len(sparql_agent.graph):,} triples")
        except Exception as e:
            print(f"❌ SPARQL agent failed: {e}")
            sparql_agent = None
            has_knowledge_graph = False
        
        print("\n💬 Chat naturally (type 'quit' to exit)")
        print("🔍 I'll show you SPARQL function calls")
        print("-" * 50)
        
        while True:
            try:
                user_input = input(f"\n💬 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print(f"\n👋 Au revoir!")
                    break
                    
                if not user_input:
                    continue
                
                print(f"\n🧠 CyberSec processing: '{user_input}'")
                response = process_fallback_input(user_input, sparql_agent, has_knowledge_graph)
                print(f"\n🤖 CyberSec: {response}")
                    
            except KeyboardInterrupt:
                print(f"\n\n👋 Au revoir!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def process_fallback_input(user_input: str, sparql_agent, has_knowledge_graph: bool) -> str:
    """Process input in fallback mode with SPARQL function calls."""
    user_lower = user_input.lower().strip()
    
    # Greetings
    if any(word in user_lower for word in ['salut', 'hello', 'hi', 'hey', 'bonjour']):
        greeting = 'Salut!' if 'salut' in user_lower else 'Hello!'
        return f"""👋 {greeting} I'm CyberSec, your cyber security intelligence agent.

🛡️ **I can help you with:**
• Analyzing 2025 cyber security threats and incidents
• Providing D3FEND-based defensive recommendations  
• Exploring attack patterns and sector impacts
• Generating auditable insights with SPARQL transparency

💬 **Just ask me naturally:**
• "What were the biggest threats this year?"
• "Show me ransomware attacks"
• "Tell me about the timeline of events"

What would you like to explore about cyber security?"""
    
    # Overview requests
    elif any(word in user_lower for word in ['overview', 'summary', 'what happened', 'show me data']):
        if not has_knowledge_graph:
            return "❌ Knowledge graph not available. Run the ontology generation pipeline first."
        
        print("🔍 Function call: get_dataset_overview()")
        result = sparql_agent.get_dataset_overview()
        
        response = f"""📊 **2025 Cyber Security Landscape Overview**

**📈 Dataset Statistics:**
• Total Events: {result.get('total_events', 0)}
• Knowledge Graph: {len(sparql_agent.graph):,} RDF triples
• Time Period: January - December 2025"""
        
        if result.get('severity_distribution'):
            response += "\n\n**⚠️ Severity Distribution:**"
            for sev in result['severity_distribution']:
                emoji = "🔴" if sev['severity'] == "critical" else "🟡"
                response += f"\n{emoji} {sev['severity'].title()}: {sev['count']} events"
        
        response += f"""

**🔍 SPARQL Audit Trail:**
• Function: get_dataset_overview() executed successfully
• Data Source: Cyber Security Knowledge Graph
• Results: Fully auditable and traceable"""
        
        return response
    
    # Timeline requests
    elif any(word in user_lower for word in ['timeline', 'when', 'chronological', 'time']):
        if not has_knowledge_graph:
            return "❌ Knowledge graph not available."
        
        print("🔍 Function call: get_timeline_analysis()")
        result = sparql_agent.get_timeline_analysis()
        
        response = "📅 **2025 Cyber Security Timeline**\n\n"
        
        if result.get('monthly_trends'):
            response += "**📊 Monthly Activity:**\n"
            for month in result['monthly_trends'][:6]:
                response += f"• {month['month']}: {month['event_count']} events ({month.get('critical_count', 0)} critical)\n"
        
        if result.get('timeline'):
            response += "\n**🕐 Recent Events:**\n"
            for event in result['timeline'][-5:]:
                emoji = "🔴" if event.get('severity') == "critical" else "🟡"
                response += f"{emoji} {event['date']} - {event['event_name']}\n"
        
        response += f"""

**🔍 SPARQL Audit Trail:**
• Function: get_timeline_analysis() executed successfully
• Total Events: {result.get('total_events', 0)}
• Data Source: Cyber Security Knowledge Graph"""
        
        return response
    
    # Specific threat searches
    elif 'satellite' in user_lower:
        return search_events_fallback('satellite_attack', sparql_agent, has_knowledge_graph)
    elif 'ransomware' in user_lower:
        return search_events_fallback('ransomware', sparql_agent, has_knowledge_graph)
    elif 'supply chain' in user_lower:
        return search_events_fallback('supply_chain_attack', sparql_agent, has_knowledge_graph)
    
    # Help requests
    elif any(word in user_lower for word in ['help', 'what can you do', 'capabilities']):
        return """🤖 **What I can help you with:**

**💬 Natural Conversation:**
• Just ask me questions naturally in English or French
• "What were the biggest cyber threats this year?"
• "Tell me about ransomware attacks"
• "Show me the timeline of events"

**🔍 Available Functions:**
• get_dataset_overview() - Dataset statistics and threat categories
• get_timeline_analysis() - Chronological analysis of events
• search_events_by_category() - Search specific threat types
• get_critical_events() - Critical incidents with D3FEND recommendations

**🛡️ Threat Categories:**
• Ransomware attacks • Supply chain compromises
• Satellite/space security • Phishing campaigns
• Critical infrastructure attacks

**🔍 Transparency:**
• Every response shows the SPARQL function I called
• Complete audit trail for all analysis
• Data traceable to original cyber security events

Just ask me anything about cyber security - I'll understand and help you!"""
    
    # Default response
    else:
        return f"""💬 I understand you're asking about: "{user_input}"

I'm specialized in cyber security intelligence. Here are some things you can ask me:

• "What happened with cyber security in 2025?"
• "Show me ransomware attacks"  
• "Tell me about satellite security incidents"
• "What's the timeline of major events?"
• "Give me an overview of the threats"

Or just say "help" to see all my capabilities. What would you like to know?"""

def search_events_fallback(category: str, sparql_agent, has_knowledge_graph: bool) -> str:
    """Search for events by category in fallback mode."""
    if not has_knowledge_graph:
        return "❌ Knowledge graph not available."
    
    print(f"🔍 Function call: search_events_by_category(category='{category}')")
    result = sparql_agent.search_events_by_criteria(category=category)
    
    if result.get('results'):
        response = f"🔍 **{category.replace('_', ' ').title()} Analysis**\n\n"
        response += f"**📊 Found {len(result['results'])} events:**\n"
        
        for event in result['results']:
            emoji = "🔴" if event.get('severity') == "critical" else "🟡"
            response += f"{emoji} {event.get('date', 'Unknown')} - {event.get('name', 'Unknown')}\n"
            if event.get('description'):
                desc = event['description'][:100] + "..." if len(event['description']) > 100 else event['description']
                response += f"   {desc}\n"
    else:
        response = f"No {category.replace('_', ' ')} events found in the dataset."
    
    response += f"""

**🔍 SPARQL Audit Trail:**
• Function: search_events_by_category('{category}') executed
• Search Criteria: {category}
• Data Source: Cyber Security Knowledge Graph"""
    
    return response

if __name__ == "__main__":
    main()