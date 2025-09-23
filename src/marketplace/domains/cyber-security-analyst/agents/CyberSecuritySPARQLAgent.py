"""
Cyber Security SPARQL Agent

An AI agent that uses SPARQL queries against the cyber security knowledge graph
to provide auditable, traceable answers about cyber security events.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import rdflib
from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery

class CyberSecuritySPARQLAgent:
    """AI agent for querying cyber security knowledge graph with SPARQL."""
    
    def __init__(self, 
                 ontology_path: str = "/Users/jrvmac/abi/storage/datastore/cyber/cyber_security_ontology.ttl",
                 queries_path: str = "/Users/jrvmac/abi/storage/datastore/cyber/sparql_queries.json"):
        """Initialize the SPARQL agent."""
        self.ontology_path = Path(ontology_path)
        self.queries_path = Path(queries_path)
        self.graph = None
        self.predefined_queries = {}
        
        # Load knowledge graph and queries
        self.load_knowledge_graph()
        self.load_predefined_queries()
    
    def load_knowledge_graph(self):
        """Load the cyber security knowledge graph."""
        if self.ontology_path.exists():
            try:
                self.graph = Graph()
                self.graph.parse(str(self.ontology_path), format="turtle")
                print(f"✅ Loaded knowledge graph: {len(self.graph)} triples")
            except Exception as e:
                print(f"❌ Error loading knowledge graph: {e}")
                self.graph = None
        else:
            print(f"⚠️  Knowledge graph not found at {self.ontology_path}")
            print("   Run the ontology generation pipeline first!")
    
    def load_predefined_queries(self):
        """Load predefined SPARQL queries."""
        if self.queries_path.exists():
            try:
                with open(self.queries_path, 'r', encoding='utf-8') as f:
                    self.predefined_queries = json.load(f)
                print(f"✅ Loaded {len(self.predefined_queries)} predefined queries")
            except Exception as e:
                print(f"❌ Error loading queries: {e}")
    
    def execute_sparql_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SPARQL query and return results."""
        if not self.graph:
            return [{"error": "Knowledge graph not loaded"}]
        
        try:
            results = self.graph.query(query)
            
            # Convert results to list of dictionaries
            result_list = []
            for row in results:
                result_dict = {}
                for i, var in enumerate(results.vars):
                    value = row[i]
                    if value:
                        result_dict[str(var)] = str(value)
                    else:
                        result_dict[str(var)] = None
                result_list.append(result_dict)
            
            return result_list
            
        except Exception as e:
            return [{"error": f"SPARQL query error: {e}"}]
    
    def get_dataset_overview(self) -> Dict[str, Any]:
        """Get comprehensive dataset overview using SPARQL."""
        if "all_events" not in self.predefined_queries:
            return {"error": "Predefined queries not available"}
        
        # Get all events
        events_query = self.predefined_queries["all_events"]
        events = self.execute_sparql_query(events_query)
        
        # Get severity distribution
        severity_query = self.predefined_queries.get("events_by_severity", "")
        severity_dist = self.execute_sparql_query(severity_query) if severity_query else []
        
        # Get sector analysis
        sector_query = self.predefined_queries.get("sector_impact_analysis", "")
        sector_analysis = self.execute_sparql_query(sector_query) if sector_query else []
        
        return {
            "total_events": len(events),
            "events": events[:10],  # First 10 events
            "severity_distribution": severity_dist,
            "sector_analysis": sector_analysis[:10],  # Top 10 sectors
            "query_audit": {
                "events_query": events_query,
                "severity_query": severity_query,
                "sector_query": sector_query,
                "execution_time": "real-time",
                "data_source": str(self.ontology_path)
            }
        }
    
    def search_events_by_criteria(self, 
                                 severity: Optional[str] = None,
                                 category: Optional[str] = None,
                                 date_range: Optional[Tuple[str, str]] = None) -> Dict[str, Any]:
        """Search events using dynamic SPARQL queries."""
        
        # Build dynamic SPARQL query
        query_parts = [
            "PREFIX cse: <https://abi.cyber-security-events.org/ontology/>",
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
            "",
            "SELECT ?event ?name ?date ?severity ?category WHERE {",
            "    ?event a cse:CyberSecurityEvent ;",
            "           cse:eventName ?name ;",
            "           cse:eventDate ?date ;",
            "           cse:severity ?severity ;",
            "           cse:category ?category ."
        ]
        
        # Add filters
        filters = []
        if severity:
            filters.append(f'FILTER(?severity = "{severity}")')
        if category:
            filters.append(f'FILTER(?category = "{category}")')
        if date_range:
            start_date, end_date = date_range
            filters.append(f'FILTER(?date >= "{start_date}"^^xsd:date && ?date <= "{end_date}"^^xsd:date)')
        
        if filters:
            query_parts.extend(["    " + f for f in filters])
        
        query_parts.extend([
            "}",
            "ORDER BY DESC(?date)"
        ])
        
        query = "\n".join(query_parts)
        results = self.execute_sparql_query(query)
        
        return {
            "results": results,
            "query_audit": {
                "sparql_query": query,
                "filters_applied": {
                    "severity": severity,
                    "category": category, 
                    "date_range": date_range
                },
                "result_count": len(results),
                "data_source": str(self.ontology_path)
            }
        }
    
    def get_attack_vector_analysis(self) -> Dict[str, Any]:
        """Analyze attack vectors and their defensive countermeasures."""
        if "attack_vectors_and_defenses" not in self.predefined_queries:
            return {"error": "Attack vector query not available"}
        
        query = self.predefined_queries["attack_vectors_and_defenses"]
        results = self.execute_sparql_query(query)
        
        # Group by attack vector
        attack_analysis = {}
        for result in results:
            attack_vector = result.get('attack_vector', 'Unknown')
            defense = result.get('defense_technique', 'Unknown')
            
            if attack_vector not in attack_analysis:
                attack_analysis[attack_vector] = {
                    "attack_vector": attack_vector,
                    "defensive_techniques": [],
                    "technique_count": 0
                }
            
            if defense not in attack_analysis[attack_vector]["defensive_techniques"]:
                attack_analysis[attack_vector]["defensive_techniques"].append(defense)
                attack_analysis[attack_vector]["technique_count"] += 1
        
        return {
            "attack_vector_analysis": list(attack_analysis.values()),
            "total_attack_vectors": len(attack_analysis),
            "query_audit": {
                "sparql_query": query,
                "raw_results": results,
                "data_source": str(self.ontology_path)
            }
        }
    
    def get_timeline_analysis(self) -> Dict[str, Any]:
        """Get chronological timeline of cyber security events."""
        if "timeline_analysis" not in self.predefined_queries:
            return {"error": "Timeline query not available"}
        
        query = self.predefined_queries["timeline_analysis"]
        results = self.execute_sparql_query(query)
        
        # Group by month for trend analysis
        monthly_trends = {}
        for result in results:
            date = result.get('date', '')
            if date:
                month = date[:7]  # YYYY-MM
                if month not in monthly_trends:
                    monthly_trends[month] = {
                        "month": month,
                        "event_count": 0,
                        "critical_count": 0,
                        "high_count": 0,
                        "events": []
                    }
                
                monthly_trends[month]["event_count"] += 1
                severity = result.get('severity', '').lower()
                if severity == 'critical':
                    monthly_trends[month]["critical_count"] += 1
                elif severity == 'high':
                    monthly_trends[month]["high_count"] += 1
                
                monthly_trends[month]["events"].append(result)
        
        return {
            "timeline": results,
            "monthly_trends": list(monthly_trends.values()),
            "total_events": len(results),
            "query_audit": {
                "sparql_query": query,
                "data_source": str(self.ontology_path)
            }
        }
    
    def get_critical_events_with_defenses(self) -> Dict[str, Any]:
        """Get critical events with their defensive recommendations."""
        if "critical_events_with_defenses" not in self.predefined_queries:
            return {"error": "Critical events query not available"}
        
        query = self.predefined_queries["critical_events_with_defenses"]
        results = self.execute_sparql_query(query)
        
        # Group by event
        critical_events = {}
        for result in results:
            event_name = result.get('event_name', 'Unknown')
            if event_name not in critical_events:
                critical_events[event_name] = {
                    "event_name": event_name,
                    "attack_vectors": [],
                    "defensive_techniques": [],
                    "defense_count": 0
                }
            
            attack_vector = result.get('attack_vector', '')
            defense_technique = result.get('defense_technique', '')
            
            if attack_vector and attack_vector not in critical_events[event_name]["attack_vectors"]:
                critical_events[event_name]["attack_vectors"].append(attack_vector)
            
            if defense_technique and defense_technique not in critical_events[event_name]["defensive_techniques"]:
                critical_events[event_name]["defensive_techniques"].append(defense_technique)
                critical_events[event_name]["defense_count"] += 1
        
        return {
            "critical_events": list(critical_events.values()),
            "total_critical_events": len(critical_events),
            "query_audit": {
                "sparql_query": query,
                "raw_results": results,
                "data_source": str(self.ontology_path)
            }
        }
    
    def execute_custom_query(self, query: str) -> Dict[str, Any]:
        """Execute a custom SPARQL query with full audit trail."""
        results = self.execute_sparql_query(query)
        
        return {
            "results": results,
            "result_count": len(results),
            "query_audit": {
                "custom_sparql_query": query,
                "execution_timestamp": "real-time",
                "data_source": str(self.ontology_path),
                "knowledge_graph_size": len(self.graph) if self.graph else 0
            }
        }
    
    def get_available_queries(self) -> Dict[str, Any]:
        """Get list of all available predefined queries."""
        return {
            "predefined_queries": list(self.predefined_queries.keys()),
            "query_descriptions": {
                "all_events": "Get all cyber security events with basic information",
                "events_by_severity": "Count events grouped by severity level",
                "attack_vectors_and_defenses": "Map attack vectors to defensive techniques",
                "sector_impact_analysis": "Analyze which sectors are most targeted",
                "timeline_analysis": "Chronological view of all events",
                "critical_events_with_defenses": "Critical events with defensive recommendations"
            },
            "custom_query_support": True,
            "audit_trail": "All queries include full audit information"
        }
    
    def natural_language_to_sparql(self, question: str) -> Dict[str, Any]:
        """Convert natural language questions to SPARQL queries."""
        question_lower = question.lower()
        
        # Simple pattern matching for common questions
        if "overview" in question_lower or "summary" in question_lower:
            return self.get_dataset_overview()
        
        elif "critical" in question_lower:
            return self.get_critical_events_with_defenses()
        
        elif "timeline" in question_lower or "chronological" in question_lower:
            return self.get_timeline_analysis()
        
        elif "attack vector" in question_lower or "defensive" in question_lower:
            return self.get_attack_vector_analysis()
        
        elif "ransomware" in question_lower:
            return self.search_events_by_criteria(category="ransomware")
        
        elif "supply chain" in question_lower:
            return self.search_events_by_criteria(category="supply_chain_attack")
        
        elif "high severity" in question_lower:
            return self.search_events_by_criteria(severity="high")
        
        else:
            return {
                "message": "Question not recognized. Available queries:",
                "available_queries": self.get_available_queries()
            }


# Convenience functions for integration
def query_cyber_events(question: str) -> Dict[str, Any]:
    """Main function for querying cyber security events with SPARQL."""
    agent = CyberSecuritySPARQLAgent()
    return agent.natural_language_to_sparql(question)

def execute_sparql(query: str) -> Dict[str, Any]:
    """Execute custom SPARQL query."""
    agent = CyberSecuritySPARQLAgent()
    return agent.execute_custom_query(query)
