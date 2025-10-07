"""
Graph Enrichment Workflow - D3FEND-CCO Semantic Mappings

Implements advanced semantic data enrichment techniques:

Capabilities:
1. Missing Process Detection - Identifies implicit processes in cyber graphs
2. Temporal Ordering Inference - Uses BFO:precedes to order events
3. Data Quality Validation - Leverages CCO semantics for validation
4. Knowledge Discovery - Enriches graphs with inferred information
"""

from typing import List, Dict, Any, Tuple
from rdflib import Graph, Namespace, OWL
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Define namespaces
D3F = Namespace("http://d3fend.mitre.org/ontologies/d3fend.owl#")
CCO = Namespace("https://www.commoncoreontologies.org/")
BFO = Namespace("http://purl.obolibrary.org/obo/")


@dataclass
class EnrichmentResult:
    """Result of graph enrichment operation."""
    added_triples: int
    missing_processes: List[Dict[str, Any]]
    temporal_orderings: List[Tuple[str, str]]
    validation_issues: List[str]
    enriched_graph: Graph


class GraphEnrichmentWorkflow:
    """
    Enriches cyber security graphs using D3FEND-CCO mappings.
    
    This workflow applies advanced semantic reasoning to:
    - Detect missing processes
    - Infer temporal ordering
    - Validate data quality
    - Discover implicit knowledge
    """
    
    def __init__(self, graph: Graph = None):
        """
        Initialize the enrichment workflow.
        
        Args:
            graph: RDF graph to enrich (optional)
        """
        self.graph = graph if graph is not None else Graph()
        self._bind_namespaces()
    
    def _bind_namespaces(self):
        """Bind common namespaces to the graph."""
        self.graph.bind("d3f", D3F)
        self.graph.bind("cco", CCO)
        self.graph.bind("bfo", BFO)
        self.graph.bind("owl", OWL)
    
    def detect_missing_processes(self) -> List[Dict[str, Any]]:
        """
        Detect missing file creation processes in the graph.
        
        When d3f:Artifact x d3f:produces y, there must be a BFO:process
        that BFO:hasOutput y. This method identifies such gaps.
        
        Returns:
            List of detected missing processes with metadata
        """
        missing_processes = []
        
        # SPARQL query from paper Figure 4 (adapted)
        query = """
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX cco: <https://www.commoncoreontologies.org/>
            
            SELECT ?artifact ?produced WHERE {
                ?artifact a d3f:Artifact ;
                         d3f:produces ?produced .
                
                # Check if a process with hasOutput already exists
                FILTER NOT EXISTS {
                    ?process a bfo:BFO_0000015 ;  # BFO:process
                            bfo:BFO_0000057 ?artifact ;  # has_participant
                            bfo:BFO_0000058 ?produced .  # has_output
                }
            }
        """
        
        try:
            results = self.graph.query(query)
            
            for row in results:
                artifact = str(row.artifact)
                produced = str(row.produced)
                
                missing_processes.append({
                    "type": "file_creation",
                    "source_artifact": artifact,
                    "output_artifact": produced,
                    "reason": "d3f:produces relation without corresponding BFO:process",
                    "severity": "medium"
                })
                
            logger.info(f"Detected {len(missing_processes)} missing processes")
            
        except Exception as e:
            logger.error(f"Error detecting missing processes: {e}")
        
        return missing_processes
    
    def add_missing_processes(self) -> int:
        """
        Add missing file creation processes to the graph.
        
        Uses SPARQL INSERT to automatically generate missing process nodes.
        
        Returns:
            Number of processes added
        """
        # SPARQL INSERT query from paper Figure 4
        insert_query = """
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX cco: <https://www.commoncoreontologies.org/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            
            INSERT {
                ?newProcess rdf:type bfo:BFO_0000015 .  # BFO:process
                ?newProcess bfo:BFO_0000057 ?x .  # has_participant
                ?newProcess bfo:BFO_0000058 ?y .  # has_output
                ?newProcess rdfs:label ?label .
                ?newProcess rdfs:comment "Auto-generated process for file creation" .
            }
            WHERE {
                ?x a d3f:Artifact ;
                   d3f:produces ?y .
                
                FILTER NOT EXISTS {
                    ?existingProcess a bfo:BFO_0000015 ;
                                    bfo:BFO_0000058 ?y .
                }
                
                BIND(IRI(CONCAT(STR(?x), "_creates_", STRAFTER(STR(?y), "#"))) AS ?newProcess)
                BIND(CONCAT("File creation process: ", STR(?x), " produces ", STR(?y)) AS ?label)
            }
        """
        
        try:
            initial_size = len(self.graph)
            self.graph.update(insert_query)
            added = len(self.graph) - initial_size
            
            logger.info(f"Added {added} missing processes to graph")
            return added
            
        except Exception as e:
            logger.error(f"Error adding missing processes: {e}")
            return 0
    
    def infer_temporal_ordering(self) -> List[Tuple[str, str]]:
        """
        Infer temporal ordering between processes.
        
        If process x has_output entity z, and entity z participates in process y,
        then process x BFO:precedes process y.
        
        Returns:
            List of (predecessor, successor) process pairs
        """
        orderings = []
        
        # SPARQL INSERT query from paper Figure 5
        insert_query = """
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            INSERT {
                ?x bfo:BFO_0000063 ?y .  # BFO:precedes
                ?x rdfs:comment "Temporally precedes (inferred via CCO semantics)" .
            }
            WHERE {
                ?x a bfo:BFO_0000015 ;  # BFO:process
                   bfo:BFO_0000058 ?z .  # has_output
                
                ?y a bfo:BFO_0000015 ;  # BFO:process
                   bfo:BFO_0000057 ?z .  # has_participant
                
                FILTER(?x != ?y)
                FILTER NOT EXISTS { ?x bfo:BFO_0000063 ?y }  # Don't duplicate
            }
        """
        
        try:
            # First, get the orderings that will be inferred
            select_query = """
                PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
                PREFIX bfo: <http://purl.obolibrary.org/obo/>
                
                SELECT ?x ?y WHERE {
                    ?x a bfo:BFO_0000015 ;
                       bfo:BFO_0000058 ?z .
                    
                    ?y a bfo:BFO_0000015 ;
                       bfo:BFO_0000057 ?z .
                    
                    FILTER(?x != ?y)
                    FILTER NOT EXISTS { ?x bfo:BFO_0000063 ?y }
                }
            """
            
            results = self.graph.query(select_query)
            for row in results:
                orderings.append((str(row.x), str(row.y)))
            
            # Now perform the insert
            self.graph.update(insert_query)
            
            logger.info(f"Inferred {len(orderings)} temporal orderings")
            
        except Exception as e:
            logger.error(f"Error inferring temporal ordering: {e}")
        
        return orderings
    
    def validate_data_quality(self) -> List[str]:
        """
        Validate data quality using CCO semantics.
        
        Checks for:
        - Domain/range violations
        - Missing required properties
        - Inconsistent classifications
        
        Returns:
            List of validation issues found
        """
        issues = []
        
        # Check for d3f:produces with wrong domain
        query1 = """
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            
            SELECT ?subject WHERE {
                ?subject d3f:produces ?object .
                ?subject a ?type .
                
                # CCO requires has_output domain to be BFO:process
                FILTER(?type != bfo:BFO_0000015)
            }
        """
        
        try:
            results = self.graph.query(query1)
            for row in results:
                issues.append(f"Domain violation: {row.subject} uses d3f:produces but is not a BFO:process")
        except Exception as e:
            logger.error(f"Error in validation query 1: {e}")
        
        # Check for DigitalEvents without Information participation
        query2 = """
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            PREFIX cco: <https://www.commoncoreontologies.org/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            
            SELECT ?event WHERE {
                ?event a d3f:DigitalEvent .
                
                FILTER NOT EXISTS {
                    ?event bfo:BFO_0000057 ?participant .
                    {
                        ?participant a cco:ont00000958 .  # Information Content Entity
                    } UNION {
                        ?participant a cco:ont00000798 .  # Information Bearing Artifact
                    }
                }
            }
        """
        
        try:
            results = self.graph.query(query2)
            for row in results:
                issues.append(f"Semantic violation: DigitalEvent {row.event} has no Information participant")
        except Exception as e:
            logger.error(f"Error in validation query 2: {e}")
        
        logger.info(f"Found {len(issues)} data quality issues")
        return issues
    
    def enrich_graph(self, input_graph: Graph = None) -> EnrichmentResult:
        """
        Perform complete graph enrichment workflow.
        
        Args:
            input_graph: Graph to enrich (uses self.graph if None)
        
        Returns:
            EnrichmentResult with all enrichment metadata
        """
        if input_graph is not None:
            self.graph = input_graph
            self._bind_namespaces()
        
        initial_size = len(self.graph)
        
        logger.info("Starting graph enrichment workflow...")
        
        # Step 1: Detect missing processes
        missing = self.detect_missing_processes()
        
        # Step 2: Add missing processes
        self.add_missing_processes()
        
        # Step 3: Infer temporal ordering
        orderings = self.infer_temporal_ordering()
        
        # Step 4: Validate data quality
        issues = self.validate_data_quality()
        
        final_size = len(self.graph)
        
        result = EnrichmentResult(
            added_triples=final_size - initial_size,
            missing_processes=missing,
            temporal_orderings=orderings,
            validation_issues=issues,
            enriched_graph=self.graph
        )
        
        logger.info(f"Enrichment complete: {result.added_triples} triples added")
        
        return result
    
    def get_enrichment_summary(self, result: EnrichmentResult) -> str:
        """
        Generate human-readable enrichment summary.
        
        Args:
            result: EnrichmentResult from enrich_graph()
        
        Returns:
            Formatted summary string
        """
        summary = f"""
🔬 **Graph Enrichment Summary** (D3FEND-CCO Methodology)

**Triples Added:** {result.added_triples}

**Missing Processes Detected:** {len(result.missing_processes)}
"""
        
        if result.missing_processes:
            summary += "\nDetected processes:\n"
            for i, proc in enumerate(result.missing_processes[:5], 1):
                summary += f"  {i}. {proc['type']}: {proc['source_artifact']} → {proc['output_artifact']}\n"
            if len(result.missing_processes) > 5:
                summary += f"  ... and {len(result.missing_processes) - 5} more\n"
        
        summary += f"\n**Temporal Orderings Inferred:** {len(result.temporal_orderings)}\n"
        
        if result.temporal_orderings:
            summary += "Sample orderings:\n"
            for i, (pred, succ) in enumerate(result.temporal_orderings[:3], 1):
                summary += f"  {i}. {pred} precedes {succ}\n"
        
        summary += f"\n**Data Quality Issues:** {len(result.validation_issues)}\n"
        
        if result.validation_issues:
            for i, issue in enumerate(result.validation_issues[:5], 1):
                summary += f"  {i}. {issue}\n"
            if len(result.validation_issues) > 5:
                summary += f"  ... and {len(result.validation_issues) - 5} more\n"
        
        return summary


def create_workflow(graph: Graph = None) -> GraphEnrichmentWorkflow:
    """
    Factory function to create GraphEnrichmentWorkflow.
    
    Args:
        graph: Optional RDF graph to enrich
    
    Returns:
        GraphEnrichmentWorkflow instance
    """
    return GraphEnrichmentWorkflow(graph)
