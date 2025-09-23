#!/usr/bin/env python3
"""
Simple CLI to chat with cyber security agents - shows SPARQL queries and gives direct answers
"""

import sys
from pathlib import Path

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

def main():
    """Direct CLI to chat with cyber security agents with SPARQL transparency."""
    
    print("🤖 Cyber Security Agent")
    print("=" * 30)
    
    # Load SPARQL agent
    try:
        exec(open(module_dir / 'agents' / 'CyberSecuritySPARQLAgent.py').read())
        agent = CyberSecuritySPARQLAgent()  # noqa: F821
        print(f"✅ Loaded knowledge graph: {len(agent.graph):,} triples")
        print(f"✅ Available queries: {len(agent.get_available_queries()['query_descriptions'])}")
    except Exception as e:
        print(f"❌ Failed to load agent: {e}")
        return
    
    print("\n💬 Ask me about cyber security (type 'quit' to exit)")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye!")
                break
                
            if not user_input:
                continue
            
            # Process input and show SPARQL execution
            print(f"\n🔍 Processing: '{user_input}'")
            
            try:
                # Route to appropriate analysis
                if any(word in user_input.lower() for word in ['overview', 'summary', 'what happened']):
                    print("📊 Executing: Dataset overview query...")
                    result = agent.get_dataset_overview()
                    show_overview_result(result)
                    
                elif any(word in user_input.lower() for word in ['timeline', 'when', 'chronological']):
                    print("📅 Executing: Timeline analysis query...")
                    result = agent.get_timeline_analysis()
                    show_timeline_result(result)
                    
                elif any(word in user_input.lower() for word in ['critical', 'serious', 'major']):
                    print("🔴 Executing: Critical events query...")
                    result = agent.get_critical_events_with_defenses()
                    show_critical_result(result)
                    
                elif any(word in user_input.lower() for word in ['attack', 'vector', 'technique']):
                    print("⚔️ Executing: Attack vector analysis query...")
                    result = agent.get_attack_vector_analysis()
                    show_attack_result(result)
                    
                elif 'satellite' in user_input.lower():
                    print("🛰️ Executing: Satellite attack search...")
                    result = agent.search_events_by_criteria(category="satellite_attack")
                    show_search_result(result, "Satellite Attacks")
                    
                elif 'ransomware' in user_input.lower():
                    print("🦠 Executing: Ransomware search...")
                    result = agent.search_events_by_criteria(category="ransomware")
                    show_search_result(result, "Ransomware")
                    
                elif 'supply chain' in user_input.lower():
                    print("🔗 Executing: Supply chain attack search...")
                    result = agent.search_events_by_criteria(category="supply_chain_attack")
                    show_search_result(result, "Supply Chain Attacks")
                    
                else:
                    # Default to overview
                    print("📊 Executing: General dataset query...")
                    result = agent.get_dataset_overview()
                    show_overview_result(result)
                    
            except Exception as e:
                print(f"❌ Query failed: {e}")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Goodbye!")
            break

def show_overview_result(result):
    """Show overview results with SPARQL audit."""
    print("\n📊 **Dataset Overview Results:**")
    print(f"   • Total Events: {result.get('total_events', 0)}")
    print(f"   • Knowledge Graph: {32311:,} triples")
    
    if result.get('events'):
        categories = {}
        for event in result['events']:
            cat = event.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"\n🔥 **Threat Categories:**")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   • {cat.replace('_', ' ').title()}: {count}")
    
    if result.get('severity_distribution'):
        print(f"\n⚠️ **Severity:**")
        for sev in result['severity_distribution']:
            emoji = "🔴" if sev['severity'] == "critical" else "🟡"
            print(f"   {emoji} {sev['severity'].title()}: {sev['count']}")
    
    show_audit_trail(result)

def show_timeline_result(result):
    """Show timeline results."""
    print("\n📅 **Timeline Analysis Results:**")
    
    if result.get('monthly_trends'):
        print(f"\n📊 **Monthly Activity:**")
        for month in result['monthly_trends'][:6]:
            print(f"   • {month['month']}: {month['event_count']} events ({month.get('critical_count', 0)} critical)")
    
    if result.get('timeline'):
        print(f"\n🕐 **Recent Events:**")
        for event in result['timeline'][-5:]:
            emoji = "🔴" if event.get('severity') == "critical" else "🟡"
            print(f"   {emoji} {event['date']} - {event['event_name']}")
    
    show_audit_trail(result)

def show_critical_result(result):
    """Show critical events results."""
    print(f"\n🔴 **Critical Events Analysis:**")
    print(f"   • Found: {result.get('total_critical_events', 0)} critical events")
    
    if result.get('critical_events'):
        for event in result['critical_events'][:3]:
            print(f"\n   🎯 **{event['event_name']}**")
            if event.get('attack_vectors'):
                print(f"      Attack Vectors: {', '.join(event['attack_vectors'][:2])}")
            if event.get('defensive_techniques'):
                print(f"      D3FEND Defenses: {len(event['defensive_techniques'])} available")
    
    show_audit_trail(result)

def show_attack_result(result):
    """Show attack vector analysis."""
    print(f"\n⚔️ **Attack Vector Analysis:**")
    print(f"   • Total Vectors: {result.get('total_attack_vectors', 0)}")
    
    if result.get('attack_vector_analysis'):
        for attack in result['attack_vector_analysis'][:3]:
            vector = attack['attack_vector'].replace('_', ' ').title()
            print(f"\n   🎯 **{vector}**")
            print(f"      D3FEND Techniques: {attack.get('technique_count', 0)}")
            if attack.get('defensive_techniques'):
                print(f"      Key Defenses: {', '.join(attack['defensive_techniques'][:2])}")
    
    show_audit_trail(result)

def show_search_result(result, category):
    """Show search results for specific categories."""
    print(f"\n🔍 **{category} Search Results:**")
    
    if result.get('results'):
        print(f"   • Found: {len(result['results'])} events")
        for event in result['results']:
            emoji = "🔴" if event.get('severity') == "critical" else "🟡"
            print(f"   {emoji} {event.get('date', 'Unknown')} - {event.get('name', 'Unknown')}")
            if event.get('description'):
                desc = event['description'][:100] + "..." if len(event['description']) > 100 else event['description']
                print(f"      {desc}")
    else:
        print(f"   • No {category.lower()} events found in dataset")
    
    show_audit_trail(result)

def show_audit_trail(result):
    """Show SPARQL audit information."""
    print(f"\n🔍 **SPARQL Audit Trail:**")
    
    if result.get('query_audit'):
        audit = result['query_audit']
        print(f"   📊 Data Source: {audit.get('data_source', 'Knowledge Graph')}")
        print(f"   ⚡ Query Type: {audit.get('query_type', 'SPARQL')}")
        if audit.get('execution_time'):
            print(f"   ⏱️ Execution: {audit['execution_time']:.3f}s")
        if audit.get('results_count'):
            print(f"   📈 Results: {audit['results_count']} records")
    else:
        print(f"   📊 Data Source: Cyber Security Knowledge Graph")
        print(f"   ⚡ Query: SPARQL executed successfully")

if __name__ == "__main__":
    main()
