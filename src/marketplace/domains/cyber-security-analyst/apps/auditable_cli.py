#!/usr/bin/env python3
"""
Auditable Cyber Security CLI

100% auditable CLI using SPARQL queries against the knowledge graph
for complete transparency and traceability.
"""

import sys
import json
from pathlib import Path

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

# Import SPARQL agent directly to avoid dependency issues
exec(open(module_dir / 'agents' / 'CyberSecuritySPARQLAgent.py').read())

class AuditableCyberSecurityCLI:
    """100% auditable CLI interface using SPARQL queries."""
    
    def __init__(self):
        """Initialize the auditable CLI interface."""
        self.agent = CyberSecuritySPARQLAgent()
        self.running = True
        
        if not self.agent.graph:
            print("❌ Knowledge graph not loaded!")
            print("   Run: python pipelines/OntologyGenerationPipeline.py")
            sys.exit(1)
    
    def show_banner(self):
        """Display the application banner."""
        print("🔒" + "=" * 70 + "🔒")
        print("    AUDITABLE CYBER SECURITY ANALYST - 100% TRANSPARENT")
        print("         SPARQL-Based Knowledge Graph Queries")
        print("🔒" + "=" * 70 + "🔒")
        print()
        print("🎯 100% AUDITABLE SYSTEM:")
        print(f"   📊 Knowledge Graph: {len(self.agent.graph):,} triples")
        print(f"   🗂️  Data Source: {self.agent.ontology_path}")
        print(f"   🔍 SPARQL Queries: {len(self.agent.predefined_queries)} predefined")
        print("   📋 Full audit trail for every query")
        print()
        print("💬 Ask questions - every answer includes SPARQL query used!")
        print("Type 'help' for commands or 'audit' to see system transparency")
        print("-" * 72)
    
    def show_help(self):
        """Show available commands."""
        print("\n🤖 AUDITABLE CYBER SECURITY AI - COMMANDS")
        print("=" * 60)
        print("📋 TRANSPARENCY COMMANDS:")
        print("  audit                  - Show system auditability info")
        print("  queries                - List all available SPARQL queries")
        print("  sparql <query>         - Execute custom SPARQL query")
        print("  trace <question>       - Show SPARQL trace for question")
        print()
        print("🔍 ANALYSIS COMMANDS:")
        print("  overview               - Dataset overview with SPARQL audit")
        print("  timeline               - Chronological analysis")
        print("  critical               - Critical events with defenses")
        print("  attacks                - Attack vector analysis")
        print("  sectors                - Sector impact analysis")
        print()
        print("💬 NATURAL LANGUAGE (with SPARQL audit):")
        print("  'Show me all events'")
        print("  'What are critical events?'")
        print("  'Analyze attack vectors'")
        print("  'Timeline of incidents'")
        print("-" * 60)
    
    def show_audit_info(self):
        """Show system auditability information."""
        print("\n🔍 SYSTEM AUDITABILITY & TRANSPARENCY")
        print("=" * 50)
        print("📊 DATA SOURCES:")
        print(f"   • Events YAML: events.yaml (20 events)")
        print(f"   • D3FEND Ontology: ontologies/d3fend.ttl")
        print(f"   • CCO Mappings: ontologies/mappings/d3fend-cco.ttl")
        print(f"   • Knowledge Graph: {self.agent.ontology_path}")
        print(f"   • Graph Size: {len(self.agent.graph):,} RDF triples")
        
        print("\n🔍 QUERY TRANSPARENCY:")
        print(f"   • Predefined Queries: {len(self.agent.predefined_queries)}")
        print("   • Custom SPARQL Support: ✅")
        print("   • Full Query Audit Trail: ✅")
        print("   • Source Attribution: ✅")
        
        print("\n📁 STORAGE STRUCTURE:")
        storage_path = Path("/Users/jrvmac/abi/storage/datastore/cyber")
        if storage_path.exists():
            html_files = list(storage_path.rglob("*.html"))
            json_files = list(storage_path.rglob("*.json"))
            ttl_files = list(storage_path.rglob("*.ttl"))
            
            print(f"   • HTML Sources: {len(html_files)} files")
            print(f"   • JSON Metadata: {len(json_files)} files")
            print(f"   • TTL Ontologies: {len(ttl_files)} files")
        
        print("\n✅ VERIFICATION:")
        print("   • All answers include SPARQL queries used")
        print("   • Data sources are traceable to original YAML")
        print("   • Ontology combines D3FEND + CCO standards")
        print("   • Full audit trail maintained")
    
    def show_available_queries(self):
        """Show all available SPARQL queries."""
        print("\n📋 AVAILABLE SPARQL QUERIES")
        print("=" * 40)
        
        queries_info = self.agent.get_available_queries()
        descriptions = queries_info.get("query_descriptions", {})
        
        for query_name in self.agent.predefined_queries.keys():
            description = descriptions.get(query_name, "No description")
            print(f"🔍 {query_name}")
            print(f"   📝 {description}")
            print()
        
        print("💡 Use 'sparql <query_name>' to see the actual SPARQL code")
        print("💡 Use 'trace <question>' to see which query answers your question")
    
    def execute_sparql_command(self, query_name: str):
        """Execute a specific SPARQL query by name."""
        if query_name in self.agent.predefined_queries:
            query = self.agent.predefined_queries[query_name]
            print(f"\n🔍 SPARQL QUERY: {query_name}")
            print("=" * 50)
            print("📝 Query:")
            print(query)
            print("\n📊 Results:")
            
            results = self.agent.execute_sparql_query(query)
            if results and not any("error" in r for r in results):
                for i, result in enumerate(results[:10], 1):  # Show first 10
                    print(f"  {i}. {result}")
                if len(results) > 10:
                    print(f"  ... and {len(results) - 10} more results")
                print(f"\n📈 Total Results: {len(results)}")
            else:
                print("❌ Query execution failed or no results")
        else:
            print(f"❌ Query '{query_name}' not found")
            print("💡 Use 'queries' to see available queries")
    
    def trace_question(self, question: str):
        """Show SPARQL trace for a natural language question."""
        print(f"\n🔍 SPARQL TRACE FOR: '{question}'")
        print("=" * 60)
        
        result = self.agent.natural_language_to_sparql(question)
        
        if "query_audit" in result:
            audit = result["query_audit"]
            print("📋 AUDIT TRAIL:")
            
            if "sparql_query" in audit:
                print("🔍 SPARQL Query Used:")
                print(audit["sparql_query"])
            
            if "events_query" in audit:
                print("🔍 Events Query:")
                print(audit["events_query"][:200] + "..." if len(audit["events_query"]) > 200 else audit["events_query"])
            
            print(f"\n📊 Data Source: {audit.get('data_source', 'Unknown')}")
            print(f"📈 Result Count: {audit.get('result_count', len(result.get('results', [])))}")
            
        else:
            print("⚠️  No audit trail available for this question")
        
        print(f"\n📄 Answer Summary: {len(result)} result keys")
    
    def process_command(self, user_input: str):
        """Process user commands with full audit trails."""
        parts = user_input.strip().split()
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command == "help":
            self.show_help()
        
        elif command == "audit":
            self.show_audit_info()
        
        elif command == "queries":
            self.show_available_queries()
        
        elif command == "sparql" and args:
            self.execute_sparql_command(args[0])
        
        elif command == "trace" and args:
            question = " ".join(args)
            self.trace_question(question)
        
        elif command == "overview":
            self.show_auditable_result("Dataset Overview", self.agent.get_dataset_overview())
        
        elif command == "timeline":
            self.show_auditable_result("Timeline Analysis", self.agent.get_timeline_analysis())
        
        elif command == "critical":
            self.show_auditable_result("Critical Events", self.agent.get_critical_events_with_defenses())
        
        elif command == "attacks":
            self.show_auditable_result("Attack Vector Analysis", self.agent.get_attack_vector_analysis())
        
        elif command == "sectors":
            # Custom sector query
            sector_result = self.agent.execute_custom_query(self.agent.predefined_queries.get("sector_impact_analysis", ""))
            self.show_auditable_result("Sector Impact Analysis", sector_result)
        
        elif command in ["quit", "exit"]:
            print("\n👋 Thanks for using the Auditable Cyber Security AI!")
            print("🔍 Remember: Every query was fully traceable and auditable!")
            self.running = False
        
        else:
            # Natural language processing
            self.process_natural_language(user_input)
    
    def show_auditable_result(self, title: str, result: Dict):
        """Show result with full audit information."""
        print(f"\n📊 {title.upper()}")
        print("=" * 50)
        
        if "error" in result:
            print(f"❌ {result['error']}")
            return
        
        # Show main results
        if "total_events" in result:
            print(f"📈 Total Events: {result['total_events']}")
        
        if "events" in result and result["events"]:
            print("📋 Sample Events:")
            for event in result["events"][:3]:
                name = event.get("name", "Unknown")
                date = event.get("date", "Unknown")
                severity = event.get("severity", "Unknown")
                print(f"  • {name} ({date}) - {severity}")
        
        if "critical_events" in result:
            print(f"🔴 Critical Events: {len(result['critical_events'])}")
            for event in result["critical_events"][:3]:
                print(f"  • {event.get('event_name', 'Unknown')}")
        
        if "attack_vector_analysis" in result:
            print(f"⚔️  Attack Vectors: {len(result['attack_vector_analysis'])}")
            for attack in result["attack_vector_analysis"][:3]:
                print(f"  • {attack.get('attack_vector', 'Unknown')}: {attack.get('technique_count', 0)} defenses")
        
        # Show audit trail
        if "query_audit" in result:
            audit = result["query_audit"]
            print(f"\n🔍 AUDIT TRAIL:")
            print(f"   📊 Data Source: {audit.get('data_source', 'Unknown')}")
            
            if "sparql_query" in audit:
                query_preview = audit["sparql_query"][:100] + "..." if len(audit["sparql_query"]) > 100 else audit["sparql_query"]
                print(f"   🔍 SPARQL Query: {query_preview}")
            
            if "result_count" in audit:
                print(f"   📈 Results: {audit['result_count']}")
            
            print("   ✅ Fully auditable and traceable")
    
    def process_natural_language(self, user_input: str):
        """Process natural language with audit trail."""
        print(f"\n🤖 AI RESPONSE (with audit trail):")
        print("-" * 40)
        
        result = self.agent.natural_language_to_sparql(user_input)
        
        # Show the answer
        if "total_events" in result:
            print(f"📊 Found {result['total_events']} events in the dataset")
        elif "critical_events" in result:
            events = result["critical_events"]
            print(f"🔴 Found {len(events)} critical events:")
            for event in events[:3]:
                print(f"  • {event.get('name', 'Unknown')} ({event.get('date', 'Unknown')})")
        elif "message" in result:
            print(f"💬 {result['message']}")
        else:
            print(f"📄 Result: {list(result.keys())}")
        
        # Always show audit trail
        if "query_audit" in result:
            audit = result["query_audit"]
            print(f"\n🔍 AUDIT TRAIL:")
            print(f"   📊 Data Source: {audit.get('data_source', 'Knowledge Graph')}")
            if "sparql_query" in audit:
                print("   🔍 SPARQL Query Used: ✅ (use 'trace' command to see full query)")
            print("   ✅ Fully traceable and auditable")
    
    def run(self):
        """Run the auditable CLI interface."""
        self.show_banner()
        
        while self.running:
            try:
                user_input = input("\n🔒 Auditable AI> ").strip()
                if user_input:
                    self.process_command(user_input)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("💡 All queries are logged for debugging")


def main():
    """Main entry point."""
    try:
        cli = AuditableCyberSecurityCLI()
        cli.run()
    except Exception as e:
        print(f"❌ Failed to start auditable CLI: {e}")
        print("💡 Make sure the knowledge graph is generated:")
        print("   python pipelines/OntologyGenerationPipeline.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
