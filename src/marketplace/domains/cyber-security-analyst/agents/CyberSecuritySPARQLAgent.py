"""
Cyber Security SPARQL Agent

Provides SPARQL query interface to cyber security knowledge graph
with complete audit trails and D3FEND integration.
"""

import logging
from pathlib import Path
from typing import Dict, Any
from rdflib import Graph, Literal

logger = logging.getLogger(__name__)

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
                logger.info("Loaded knowledge graph: %s triples", len(self.graph))
            except Exception as e:
                logger.error("Failed to load ontology: %s", e)
                self.graph = None
        else:
            logger.error("Ontology file not found: %s", self.ontology_path)
            self.graph = None
        
        # Load predefined queries
        self.queries = self._load_predefined_queries()
        logger.info("Loaded %s predefined queries", len(self.queries))
    
    def _load_predefined_queries(self) -> Dict[str, str]:
        """Load predefined SPARQL queries."""
        return {
            "dataset_overview": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?category ?severity WHERE {
                    ?event rdf:type cse:CyberSecurityEvent ;
                           cse:eventName ?name ;
                           cse:eventDate ?date ;
                           cse:category ?category ;
                           cse:severity ?severity .
                }
                ORDER BY ?date
            """,
            
            "timeline_analysis": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?severity WHERE {
                    ?event rdf:type cse:CyberSecurityEvent ;
                           cse:eventName ?name ;
                           cse:eventDate ?date ;
                           cse:severity ?severity .
                }
                ORDER BY ?date
            """,
            
            "critical_events": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?event ?name ?date ?category ?attackVector ?attackVectorLabel ?defensiveTechnique ?defensiveTechniqueLabel WHERE {
                    ?event rdf:type cse:CyberSecurityEvent ;
                           cse:eventName ?name ;
                           cse:eventDate ?date ;
                           cse:category ?category ;
                           cse:severity "critical" ;
                           cse:hasAttackVector ?attackVector .
                    OPTIONAL { ?event cse:hasDefensiveTechnique ?defensiveTechnique . }
                    OPTIONAL { ?attackVector rdfs:label ?attackVectorLabel . }
                    OPTIONAL { ?defensiveTechnique rdfs:label ?defensiveTechniqueLabel . }
                }
                ORDER BY ?date
            """,
            
            "attack_vectors": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?attackVector ?attackVectorLabel ?defensiveTechnique ?defensiveTechniqueLabel WHERE {
                    ?event rdf:type cse:CyberSecurityEvent ;
                           cse:hasAttackVector ?attackVector .
                    OPTIONAL { ?attackVector rdfs:label ?attackVectorLabel . }
                    OPTIONAL {
                        { ?event cse:hasDefensiveTechnique ?defensiveTechnique . }
                        UNION
                        { ?attackVector cse:mitigatedBy ?defensiveTechnique . }
                        OPTIONAL { ?defensiveTechnique rdfs:label ?defensiveTechniqueLabel . }
                    }
                }
            """,
            
            "search_by_category": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?event ?name ?date ?description ?severity ?category WHERE {
                    ?event rdf:type cse:CyberSecurityEvent ;
                           cse:eventName ?name ;
                           cse:eventDate ?date ;
                           cse:description ?description ;
                           cse:severity ?severity ;
                           cse:category ?category .
                    %FILTERS%
                }
                ORDER BY ?date
            """,
            
            "severity_distribution": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                SELECT ?severity (COUNT(?event) as ?count) WHERE {
                    ?event rdf:type cse:CyberSecurityEvent ;
                           cse:severity ?severity .
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
            "search_by_category": "Search events with category and severity filters",
            "severity_distribution": "Get distribution of events by severity level"
        }
        
        return {
            "query_descriptions": descriptions,
            "total_queries": len(self.queries)
        }
    
    def get_dataset_overview(self) -> Dict[str, Any]:
        """Get comprehensive dataset overview."""
        if self.graph is None:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            # Execute overview query
            results = list(self.graph.query(self.queries["dataset_overview"]))
            
            events = []
            for row in results:
                events.append({
                    "event": str(row[0]),
                    "name": str(row[1]),
                    "date": str(row[2]),
                    "category": str(row[3]),
                    "severity": str(row[4])
                })
            
            # Get severity distribution
            sev_results = list(self.graph.query(self.queries["severity_distribution"]))
            severity_dist = []
            for row in sev_results:
                count_term = row[1]
                try:
                    count_val = count_term.toPython()  # type: ignore[attr-defined]
                except Exception:
                    count_val = count_term
                try:
                    count_int = int(count_val)
                except Exception:
                    count_int = int(str(count_val))
                severity_dist.append({
                    "severity": str(row[0]),
                    "count": count_int
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
        if self.graph is None:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            filters = []
            if category:
                filters.append(f"FILTER(?category = {Literal(category).n3()})")
            if severity:
                filters.append(f"FILTER(?severity = {Literal(severity).n3()})")

            filters_clause = "\n                    ".join(filters) if filters else ""
            query = self.queries["search_by_category"].replace("%FILTERS%", filters_clause)

            results = list(self.graph.query(query))

            events = []
            for row in results:
                events.append({
                    "event": str(row.event),
                    "name": str(row.name),
                    "date": str(row.date),
                    "description": str(getattr(row, "description", "")),
                    "severity": str(row.severity),
                    "category": str(row.category)
                })

            return {
                "results": events,
                "total_results": len(events),
                "search_criteria": {"category": category, "severity": severity},
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL Event Search",
                    "results_count": len(events)
                }
            }

        except Exception as e:
            return {"error": f"Search failed: {e}"}
    
    def get_timeline_analysis(self) -> Dict[str, Any]:
        """Get timeline analysis of cyber security events."""
        if self.graph is None:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            results = list(self.graph.query(self.queries["timeline_analysis"]))
            
            timeline = []
            monthly_counts = {}
            
            for row in results:
                event = {
                    "event": str(row.event),
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
                if str(row.severity).lower() == "critical":
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
        if self.graph is None:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            results = list(self.graph.query(self.queries["critical_events"]))

            events_by_id: Dict[str, Dict[str, Any]] = {}
            for row in results:
                event_iri = str(row.event)
                event_entry = events_by_id.setdefault(event_iri, {
                    "event": event_iri,
                    "event_name": str(row.name),
                    "date": str(row.date),
                    "category": str(row.category),
                    "attack_vectors": [],
                    "defensive_techniques": []
                })

                attack_vector_label = getattr(row, "attackVectorLabel", None) or getattr(row, "attackVector", None)
                if attack_vector_label is not None:
                    attack_vector_value = str(attack_vector_label)
                    if attack_vector_value not in event_entry["attack_vectors"]:
                        event_entry["attack_vectors"].append(attack_vector_value)

                defensive_label = getattr(row, "defensiveTechniqueLabel", None) or getattr(row, "defensiveTechnique", None)
                if defensive_label is not None:
                    defensive_value = str(defensive_label)
                    if defensive_value not in event_entry["defensive_techniques"]:
                        event_entry["defensive_techniques"].append(defensive_value)

            critical_events = list(events_by_id.values())

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
        if self.graph is None:
            return {"error": "Knowledge graph not loaded"}
        
        try:
            results = list(self.graph.query(self.queries["attack_vectors"]))

            vector_analysis: Dict[str, Dict[str, Any]] = {}
            for row in results:
                attack_vector_term = getattr(row, "attackVector", None)
                if attack_vector_term is None:
                    continue

                attack_vector_uri = str(attack_vector_term)
                attack_vector_label = getattr(row, "attackVectorLabel", None)
                attack_vector_display = str(attack_vector_label or attack_vector_term)

                vector_entry = vector_analysis.setdefault(attack_vector_uri, {
                    "attack_vector": attack_vector_display,
                    "attack_vector_uri": attack_vector_uri,
                    "defensive_techniques": [],
                    "defensive_technique_uris": []
                })

                # Upgrade label if a better one is encountered later
                if attack_vector_label and vector_entry["attack_vector"] == vector_entry["attack_vector_uri"]:
                    vector_entry["attack_vector"] = attack_vector_display

                defensive_term = getattr(row, "defensiveTechnique", None)
                if defensive_term is None:
                    continue

                defensive_uri = str(defensive_term)
                defensive_label = getattr(row, "defensiveTechniqueLabel", None)
                defensive_display = str(defensive_label or defensive_term)

                if defensive_uri not in vector_entry["defensive_technique_uris"]:
                    vector_entry["defensive_technique_uris"].append(defensive_uri)
                    vector_entry["defensive_techniques"].append(defensive_display)

            attack_vector_analysis = []
            for entry in vector_analysis.values():
                entry["technique_count"] = len(entry["defensive_technique_uris"])
                attack_vector_analysis.append(entry)

            return {
                "attack_vector_analysis": attack_vector_analysis,
                "total_attack_vectors": len(attack_vector_analysis),
                "query_audit": {
                    "data_source": "Cyber Security Knowledge Graph",
                    "query_type": "SPARQL Attack Vector Analysis",
                    "results_count": len(attack_vector_analysis)
                }
            }

        except Exception as e:
            return {"error": f"Attack vector analysis failed: {e}"}
