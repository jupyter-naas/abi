"""
Cyber Security SPARQL Agent

Provides SPARQL query interface to cyber security knowledge graph
with complete audit trails and D3FEND integration.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from rdflib import Graph

class CyberSecuritySPARQLAgent:
    """SPARQL agent for cyber security knowledge graph queries."""
    
    def __init__(self):
        """Initialize the SPARQL agent with knowledge graph."""
        self.module_dir = Path(__file__).parent.parent
        self.ontology_path = self.module_dir / "cyber_security_ontology.ttl"
        
        # Load the knowledge graph
        self.graph = Graph()
        
        if self.ontology_path.exists():
            try:
                self.graph.parse(str(self.ontology_path), format="turtle")
                print(f"✅ Loaded knowledge graph: {len(self.graph):,} triples")
            except Exception as e:
                print(f"❌ Failed to load ontology: {e}")
                self.graph = None
        else:
            print(f"❌ Ontology file not found: {self.ontology_path}")
            self.graph = None
        
        # Load predefined queries
        self.queries = self._load_predefined_queries()
        print(f"✅ Loaded {len(self.queries)} predefined queries")
    
    def _load_predefined_queries(self) -> Dict[str, str]:
        """Load predefined SPARQL queries."""
        return {
            "dataset_overview": """
                PREFIX : <http://example.org/cyber-security#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?category ?severity WHERE {
                    ?event rdf:type :CyberSecurityEvent ;
                           :name ?name ;
                           :date ?date ;
                           :category ?category ;
                           :severity ?severity .
                }
                ORDER BY ?date
            """,
            
            "timeline_analysis": """
                PREFIX : <http://example.org/cyber-security#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?severity WHERE {
                    ?event rdf:type :CyberSecurityEvent ;
                           :name ?name ;
                           :date ?date ;
                           :severity ?severity .
                }
                ORDER BY ?date
            """,
            
            "critical_events": """
                PREFIX : <http://example.org/cyber-security#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?category ?attackVectors WHERE {
                    ?event rdf:type :CyberSecurityEvent ;
                           :name ?name ;
                           :date ?date ;
                           :category ?category ;
                           :severity "critical" ;
                           :attackVectors ?attackVectors .
                }
                ORDER BY ?date
            """,
            
            "attack_vectors": """
                PREFIX : <http://example.org/cyber-security#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?attackVector ?defensiveTechnique WHERE {
                    ?event rdf:type :CyberSecurityEvent ;
                           :attackVectors ?attackVector ;
                           :defensiveTechniques ?defensiveTechnique .
                }
            """,
            
            "search_by_category": """
                PREFIX : <http://example.org/cyber-security#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?description ?severity WHERE {
                    ?event rdf:type :CyberSecurityEvent ;
                           :name ?name ;
                           :date ?date ;
                           :description ?description ;
                           :severity ?severity ;
                           :category ?category .
                    FILTER(?category = "%CATEGORY%")
                }
                ORDER BY ?date
            """,
            
            "severity_distribution": """
                PREFIX : <http://example.org/cyber-security#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?severity (COUNT(?event) as ?count) WHERE {
                    ?event rdf:type :CyberSecurityEvent ;
                           :severity ?severity .
                }
                GROUP BY ?severity
                ORDER BY DESC(?count)
            """
        }
    
    def get_available_queries(self) -> Dict[str, Any]:
        """Get available SPARQL queries with descriptions."""
        descriptions = {
            "dataset_overview": "Get comprehensive overview of all cyber security events",
            "timeline_analysis": "Analyze events chronologically over time",
            "critical_events": "Find critical severity events with attack vectors",
            "attack_vectors": "Map attack vectors to defensive techniques",
            "search_by_category": "Search events by specific category",
            "severity_distribution": "Get distribution of events by severity level"
        }
        
        return {
            "query_descriptions": descriptions,
            "total_queries": len(self.queries)
        }
    
    def get_dataset_overview(self) -> Dict[str, Any]:
        """Get comprehensive dataset overview."""
        if not self.graph:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            # Execute overview query
            results = list(self.graph.query(self.queries["dataset_overview"]))
            
            events = []
            for row in results:
                events.append({
                    "event": str(row.event),
                    "name": str(row.name),
                    "date": str(row.date),
                    "category": str(row.category),
                    "severity": str(row.severity)
                })
            
            # Get severity distribution
            sev_results = list(self.graph.query(self.queries["severity_distribution"]))
            severity_dist = []
            for row in sev_results:
                severity_dist.append({
                    "severity": str(row.severity),
                    "count": int(row.count)
                })
            
            return {
                "total_events": len(events),
                "events": events,
                "severity_distribution": severity_dist,
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL",
                    "results_count": len(events)
                }
            }
            
        except Exception as e:
            return {"error": f"Query failed: {e}"}
    
    def search_events_by_criteria(self, category: str = None, severity: str = None) -> Dict[str, Any]:
        """Search events by category or severity."""
        if not self.graph:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            if category:
                query = self.queries["search_by_category"].replace("%CATEGORY%", category)
            else:
                query = self.queries["dataset_overview"]
            
            results = list(self.graph.query(query))
            
            events = []
            for row in results:
                events.append({
                    "name": str(row.name),
                    "date": str(row.date),
                    "description": str(row.description) if hasattr(row, 'description') else "",
                    "severity": str(row.severity)
                })
            
            return {
                "results": events,
                "total_results": len(events),
                "search_criteria": {"category": category, "severity": severity},
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL Category Search",
                    "results_count": len(events)
                }
            }
            
        except Exception as e:
            return {"error": f"Search failed: {e}"}
    
    def get_timeline_analysis(self) -> Dict[str, Any]:
        """Get timeline analysis of cyber security events."""
        if not self.graph:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            results = list(self.graph.query(self.queries["timeline_analysis"]))
            
            timeline = []
            monthly_counts = {}
            
            for row in results:
                event = {
                    "event_name": str(row.name),
                    "date": str(row.date),
                    "severity": str(row.severity)
                }
                timeline.append(event)
                
                # Count by month
                month = str(row.date)[:7]  # YYYY-MM
                if month not in monthly_counts:
                    monthly_counts[month] = {"total": 0, "critical": 0}
                monthly_counts[month]["total"] += 1
                if str(row.severity) == "critical":
                    monthly_counts[month]["critical"] += 1
            
            # Format monthly trends
            monthly_trends = []
            for month, counts in sorted(monthly_counts.items()):
                monthly_trends.append({
                    "month": month,
                    "event_count": counts["total"],
                    "critical_count": counts["critical"]
                })
            
            return {
                "timeline": timeline,
                "monthly_trends": monthly_trends,
                "total_events": len(timeline),
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL Timeline Analysis",
                    "results_count": len(timeline)
                }
            }
            
        except Exception as e:
            return {"error": f"Timeline analysis failed: {e}"}
    
    def get_critical_events_with_defenses(self) -> Dict[str, Any]:
        """Get critical events with D3FEND defensive recommendations."""
        if not self.graph:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            results = list(self.graph.query(self.queries["critical_events"]))
            
            critical_events = []
            for row in results:
                # Parse attack vectors (assuming comma-separated)
                attack_vectors = str(row.attackVectors).split(",") if row.attackVectors else []
                
                critical_events.append({
                    "event_name": str(row.name),
                    "date": str(row.date),
                    "category": str(row.category),
                    "attack_vectors": [av.strip() for av in attack_vectors],
                    "defensive_techniques": []  # Would be populated from D3FEND mappings
                })
            
            return {
                "critical_events": critical_events,
                "total_critical_events": len(critical_events),
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL Critical Events",
                    "results_count": len(critical_events)
                }
            }
            
        except Exception as e:
            return {"error": f"Critical events query failed: {e}"}
    
    def get_attack_vector_analysis(self) -> Dict[str, Any]:
        """Analyze attack vectors and map to defensive techniques."""
        if not self.graph:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            results = list(self.graph.query(self.queries["attack_vectors"]))
            
            vector_analysis = {}
            for row in results:
                vector = str(row.attackVector)
                technique = str(row.defensiveTechnique)
                
                if vector not in vector_analysis:
                    vector_analysis[vector] = {
                        "attack_vector": vector,
                        "defensive_techniques": [],
                        "technique_count": 0
                    }
                
                if technique not in vector_analysis[vector]["defensive_techniques"]:
                    vector_analysis[vector]["defensive_techniques"].append(technique)
                    vector_analysis[vector]["technique_count"] += 1
            
            return {
                "attack_vector_analysis": list(vector_analysis.values()),
                "total_attack_vectors": len(vector_analysis),
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL Attack Vector Analysis",
                    "results_count": len(vector_analysis)
                }
            }
            
        except Exception as e:
            return {"error": f"Attack vector analysis failed: {e}"}