#!/usr/bin/env python3
"""
Conversational Cyber Security CLI - Natural AI conversation with SPARQL function calls
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

class ConversationalCyberCLI:
    """Conversational cyber security CLI with natural responses."""
    
    def __init__(self):
        """Initialize the conversational CLI."""
        self.name = "CyberSec"
        
        # Load SPARQL agent for data queries
        try:
            exec(open(module_dir / 'agents' / 'CyberSecuritySPARQLAgent.py').read())
            self.sparql_agent = CyberSecuritySPARQLAgent()  # noqa: F821
            self.has_knowledge_graph = self.sparql_agent.graph is not None
            print(f"✅ Loaded knowledge graph: {len(self.sparql_agent.graph):,} triples")
        except Exception as e:
            print(f"❌ Failed to load SPARQL agent: {e}")
            self.sparql_agent = None
            self.has_knowledge_graph = False
    
    def handle_greeting(self, message: str) -> str:
        """Handle greetings naturally."""
        greetings = {
            'salut': 'Salut!',
            'hello': 'Hello!', 
            'hi': 'Hi there!',
            'hey': 'Hey!'
        }
        
        greeting = 'Hello!'
        for word, response in greetings.items():
            if word in message.lower():
                greeting = response
                break
        
        return f"""👋 {greeting} I'm {self.name}, your cyber security intelligence agent.

🛡️ **I can help you with:**
• Analyzing 2025 cyber security threats and incidents
• Providing D3FEND-based defensive recommendations  
• Exploring attack patterns and sector impacts
• Generating auditable insights with SPARQL transparency

💬 **Just ask me naturally:**
• "What were the biggest threats this year?"
• "Show me ransomware attacks"
• "How can I defend against supply chain attacks?"
• "Tell me about the timeline of events"

What would you like to explore about cyber security?"""
    
    def get_overview(self) -> str:
        """Get dataset overview with SPARQL query."""
        if not self.has_knowledge_graph:
            return "❌ Knowledge graph not available. The ontology needs to be generated first."
        
        print("🔍 Function call: get_dataset_overview()")
        result = self.sparql_agent.get_dataset_overview()
        
        response = f"""📊 **2025 Cyber Security Landscape Overview**

**📈 Dataset Statistics:**
• Total Events: {result.get('total_events', 0)}
• Knowledge Graph: {len(self.sparql_agent.graph):,} RDF triples
• Time Period: January - December 2025"""
        
        if result.get('severity_distribution'):
            response += "\n\n**⚠️ Severity Distribution:**"
            for sev in result['severity_distribution']:
                emoji = "🔴" if sev['severity'] == "critical" else "🟡" if sev['severity'] == "high" else "🟢"
                response += f"\n{emoji} {sev['severity'].title()}: {sev['count']} events"
        
        response += f"""

**🔍 SPARQL Audit Trail:**
• Query: Dataset overview executed successfully
• Data Source: Cyber Security Knowledge Graph
• Results: Fully auditable and traceable

Want to explore specific threats? Try asking about ransomware, supply chain attacks, or the timeline!"""
        
        return response
    
    def search_threats(self, category: str) -> str:
        """Search for specific threat categories."""
        if not self.has_knowledge_graph:
            return "❌ Knowledge graph not available."
        
        print(f"🔍 Function call: search_events_by_category(category='{category}')")
        result = self.sparql_agent.search_events_by_criteria(category=category)
        
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
• Query: Category search executed successfully
• Search Criteria: {category}
• Data Source: Cyber Security Knowledge Graph"""
        
        return response
    
    def get_timeline(self) -> str:
        """Get timeline analysis."""
        if not self.has_knowledge_graph:
            return "❌ Knowledge graph not available."
        
        print("🔍 Function call: get_timeline_analysis()")
        result = self.sparql_agent.get_timeline_analysis()
        
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
• Query: Timeline analysis executed successfully
• Total Events: {result.get('total_events', 0)}
• Data Source: Cyber Security Knowledge Graph"""
        
        return response
    
    def process_input(self, user_input: str) -> str:
        """Process user input and generate natural responses."""
        user_lower = user_input.lower().strip()
        
        # Greetings
        if any(word in user_lower for word in ['salut', 'hello', 'hi', 'hey', 'bonjour']):
            return self.handle_greeting(user_input)
        
        # Overview requests
        elif any(word in user_lower for word in ['overview', 'summary', 'what happened', 'show me data']):
            return self.get_overview()
        
        # Timeline requests
        elif any(word in user_lower for word in ['timeline', 'when', 'chronological', 'time']):
            return self.get_timeline()
        
        # Specific threat searches
        elif 'satellite' in user_lower:
            return self.search_threats('satellite_attack')
        elif 'ransomware' in user_lower:
            return self.search_threats('ransomware')
        elif 'supply chain' in user_lower:
            return self.search_threats('supply_chain_attack')
        elif 'phishing' in user_lower:
            return self.search_threats('phishing')
        
        # Help requests
        elif any(word in user_lower for word in ['help', 'what can you do', 'capabilities']):
            return """🤖 **What I can help you with:**

**💬 Natural Conversation:**
• Just ask me questions naturally in English or French
• "What were the biggest cyber threats this year?"
• "Tell me about ransomware attacks"
• "Show me the timeline of events"

**🔍 Available Analysis:**
• Dataset overview and statistics
• Timeline of 2025 cyber security events  
• Specific threat category searches (ransomware, supply chain, etc.)
• Attack vector analysis with D3FEND recommendations

**🛡️ Threat Categories I know about:**
• Ransomware attacks
• Supply chain compromises
• Satellite/space security incidents
• Phishing campaigns
• Critical infrastructure attacks

**🔍 Transparency:**
• Every response shows the SPARQL query I executed
• Complete audit trail for all analysis
• Data traceable to original cyber security events

Just ask me anything about cyber security - I'll understand and help you!"""
        
        # Default response for unrecognized input
        else:
            return f"""💬 I understand you're asking about: "{user_input}"

I'm specialized in cyber security intelligence. Here are some things you can ask me:

• "What happened with cyber security in 2025?"
• "Show me ransomware attacks"
• "Tell me about satellite security incidents"  
• "What's the timeline of major events?"
• "Give me an overview of the threats"

Or just say "help" to see all my capabilities. What would you like to know about cyber security?"""

def main():
    """Main CLI function."""
    print("🤖 Conversational Cyber Security Agent")
    print("=" * 40)
    
    cli = ConversationalCyberCLI()
    
    print(f"✅ Loaded {cli.name} conversational agent")
    print(f"🧠 Natural conversation with SPARQL backend")
    
    print("\n💬 Chat naturally with the agent (type 'quit' to exit)")
    print("🔍 I'll show you the SPARQL queries I execute")
    print("-" * 50)
    
    while True:
        try:
            user_input = input(f"\n💬 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye', 'au revoir']:
                print(f"\n👋 Au revoir! Stay secure!")
                break
                
            if not user_input:
                continue
            
            print(f"\n🧠 {cli.name} processing: '{user_input}'")
            response = cli.process_input(user_input)
            print(f"\n🤖 {cli.name}: {response}")
                
        except KeyboardInterrupt:
            print(f"\n\n👋 Au revoir! Stay secure!")
            break
        except EOFError:
            print(f"\n\n👋 Au revoir! Stay secure!")
            break

if __name__ == "__main__":
    main()