from abi.services.reasoner.ReasonerPorts import (
    IReasonerPort,
    ReasoningConfiguration,
    ReasoningResult,
    InconsistencyType
)
from rdflib import Graph, RDF, RDFS
from typing import Set, List
import time
import tempfile
import os
from abi import logger

try:
    import owlready2
    from owlready2 import sync_reasoner_hermit, sync_reasoner_pellet
    OWLREADY2_AVAILABLE = True
except ImportError:
    OWLREADY2_AVAILABLE = False
    logger.warning("Owlready2 not available. Install with: pip install owlready2")


class Owlready2ReasonerAdapter(IReasonerPort):
    """
    Adapter for Owlready2-based OWL reasoning.
    
    This adapter provides integration with Owlready2's reasoning capabilities,
    including HermiT and Pellet reasoners. It's optimized for BFO-based ontologies
    and provides comprehensive OWL 2 DL reasoning support.
    
    Features:
    - HermiT and Pellet reasoner backends
    - Consistency checking and explanation
    - Class hierarchy inference
    - Individual classification
    - Optimized for BFO ontology patterns
    
    Note: Requires Java runtime for HermiT/Pellet reasoners.
    """
    
    def __init__(self, reasoner_type: str = "hermit", java_memory: str = "2G"):
        """Initialize the Owlready2 reasoner adapter.
        
        Args:
            reasoner_type: Type of reasoner to use ("hermit" or "pellet")
            java_memory: Memory allocation for Java reasoner
        """
        if not OWLREADY2_AVAILABLE:
            raise ImportError("Owlready2 is required but not installed")
        
        self.reasoner_type = reasoner_type.lower()
        self.java_memory = java_memory
        self.world = None
        self.ontology = None
        
        # Set Java memory for reasoners
        owlready2.JAVA_EXE = "java"
        if java_memory:
            owlready2.reasoning.JAVA_MEMORY = java_memory
        
        logger.info(f"Owlready2ReasonerAdapter initialized with {reasoner_type} reasoner")
    
    def initialize(self, base_ontology: Graph) -> bool:
        """Initialize the reasoner with a base ontology."""
        try:
            # Create a new world
            self.world = owlready2.World()
            
            # Convert RDFLib graph to Owlready2 ontology
            with tempfile.NamedTemporaryFile(mode='w', suffix='.owl', delete=False) as tmp:
                # Serialize to OWL/XML which Owlready2 handles best
                owl_content = base_ontology.serialize(format='xml')
                tmp.write(owl_content)
                tmp_path = tmp.name
            
            try:
                # Load ontology into Owlready2
                self.ontology = self.world.get_ontology(f"file://{tmp_path}").load()
                logger.info(f"Base ontology loaded successfully with {len(list(self.ontology.classes()))} classes")
                return True
                
            finally:
                # Clean up temporary file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Failed to initialize reasoner: {str(e)}")
            return False
    
    def _convert_rdflib_to_owlready2(self, graph: Graph) -> owlready2.Ontology:
        """Convert RDFLib graph to Owlready2 ontology."""
        # Create a temporary world for this operation
        temp_world = owlready2.World()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.owl', delete=False) as tmp:
            owl_content = graph.serialize(format='xml')
            tmp.write(owl_content)
            tmp_path = tmp.name
        
        try:
            ontology = temp_world.get_ontology(f"file://{tmp_path}").load()
            return ontology
        finally:
            os.unlink(tmp_path)
    
    def _convert_owlready2_to_rdflib(self, ontology: owlready2.Ontology) -> Graph:
        """Convert Owlready2 ontology to RDFLib graph."""
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.owl', delete=False) as tmp:
            ontology.save(file=tmp.name, format="rdfxml")
            tmp_path = tmp.name
        
        try:
            graph = Graph()
            graph.parse(tmp_path, format='xml')
            return graph
        finally:
            os.unlink(tmp_path)
    
    def reason(self, ontology: Graph, config: ReasoningConfiguration) -> ReasoningResult:
        """Perform reasoning on the given ontology."""
        start_time = time.time()
        
        try:
            # Convert to Owlready2 format
            owl_ontology = self._convert_rdflib_to_owlready2(ontology)
            
            # Choose reasoner based on configuration
            if self.reasoner_type == "hermit":
                reasoner_func = sync_reasoner_hermit
            elif self.reasoner_type == "pellet":
                reasoner_func = sync_reasoner_pellet
            else:
                raise ValueError(f"Unsupported reasoner type: {self.reasoner_type}")
            
            # Set up reasoning parameters
            with owl_ontology:
                try:
                    # Perform reasoning
                    reasoner_func(infer_property_values=True, 
                                infer_data_property_values=True,
                                debug=False)
                    
                    is_consistent = True
                    inconsistencies = []
                    
                except owlready2.OwlReadyInconsistentOntologyError:
                    is_consistent = False
                    inconsistencies = [InconsistencyType.LOGICAL_CONTRADICTION]
                    logger.warning("Ontology found to be inconsistent")
                
                except Exception as e:
                    logger.error(f"Reasoning failed: {str(e)}")
                    raise
            
            # Convert result back to RDFLib
            inferred_graph = self._convert_owlready2_to_rdflib(owl_ontology)
            
            reasoning_time = time.time() - start_time
            
            result = ReasoningResult(
                inferred_graph=inferred_graph,
                is_consistent=is_consistent,
                reasoning_time=reasoning_time,
                inconsistencies=inconsistencies,
                warnings=[],
                metadata={
                    "reasoner_type": self.reasoner_type,
                    "original_triples": len(ontology),
                    "inferred_triples": len(inferred_graph),
                    "new_triples": len(inferred_graph) - len(ontology)
                }
            )
            
            logger.info(f"Reasoning completed in {reasoning_time:.2f}s using {self.reasoner_type}")
            return result
            
        except Exception as e:
            logger.error(f"Reasoning operation failed: {str(e)}")
            # Return a basic result indicating failure
            return ReasoningResult(
                inferred_graph=ontology,  # Return original graph
                is_consistent=False,
                reasoning_time=time.time() - start_time,
                inconsistencies=[InconsistencyType.LOGICAL_CONTRADICTION],
                warnings=[f"Reasoning failed: {str(e)}"],
                metadata={"error": str(e)}
            )
    
    def check_consistency(self, ontology: Graph) -> bool:
        """Check if the ontology is logically consistent."""
        try:
            owl_ontology = self._convert_rdflib_to_owlready2(ontology)
            
            with owl_ontology:
                if self.reasoner_type == "hermit":
                    sync_reasoner_hermit()
                elif self.reasoner_type == "pellet":
                    sync_reasoner_pellet()
                
                return True  # If we get here, it's consistent
                
        except owlready2.OwlReadyInconsistentOntologyError:
            return False
        except Exception as e:
            logger.error(f"Consistency check failed: {str(e)}")
            return False
    
    def get_unsatisfiable_classes(self, ontology: Graph) -> Set[str]:
        """Get classes that are unsatisfiable (equivalent to Nothing)."""
        try:
            owl_ontology = self._convert_rdflib_to_owlready2(ontology)
            unsatisfiable = set()
            
            with owl_ontology:
                if self.reasoner_type == "hermit":
                    sync_reasoner_hermit()
                elif self.reasoner_type == "pellet":
                    sync_reasoner_pellet()
                
                # Check each class for satisfiability
                for cls in owl_ontology.classes():
                    # A class is unsatisfiable if it's equivalent to Nothing
                    if owlready2.Nothing in cls.equivalent_to:
                        unsatisfiable.add(str(cls.iri))
            
            return unsatisfiable
            
        except Exception as e:
            logger.error(f"Failed to get unsatisfiable classes: {str(e)}")
            return set()
    
    def infer_class_hierarchy(self, ontology: Graph) -> Graph:
        """Infer the complete class hierarchy including implicit subclass relations."""
        try:
            owl_ontology = self._convert_rdflib_to_owlready2(ontology)
            
            with owl_ontology:
                if self.reasoner_type == "hermit":
                    sync_reasoner_hermit()
                elif self.reasoner_type == "pellet":
                    sync_reasoner_pellet()
                
                # Get inferred class hierarchy
                hierarchy_graph = Graph()
                
                for cls in owl_ontology.classes():
                    # Add inferred superclasses
                    for parent in cls.is_a:
                        if isinstance(parent, owlready2.ThingClass):
                            hierarchy_graph.add((
                                cls.iri,
                                RDFS.subClassOf,
                                parent.iri
                            ))
                
                return hierarchy_graph
                
        except Exception as e:
            logger.error(f"Failed to infer class hierarchy: {str(e)}")
            return Graph()
    
    def classify_individuals(self, ontology: Graph) -> Graph:
        """Classify individuals to their most specific classes."""
        try:
            owl_ontology = self._convert_rdflib_to_owlready2(ontology)
            
            with owl_ontology:
                if self.reasoner_type == "hermit":
                    sync_reasoner_hermit()
                elif self.reasoner_type == "pellet":
                    sync_reasoner_pellet()
                
                # Get inferred individual classifications
                classification_graph = Graph()
                
                for individual in owl_ontology.individuals():
                    # Add inferred types
                    for cls in individual.is_a:
                        if isinstance(cls, owlready2.ThingClass):
                            classification_graph.add((
                                individual.iri,
                                RDF.type,
                                cls.iri
                            ))
                
                return classification_graph
                
        except Exception as e:
            logger.error(f"Failed to classify individuals: {str(e)}")
            return Graph()
    
    def explain_inconsistency(self, ontology: Graph) -> List[str]:
        """Provide explanations for why the ontology is inconsistent."""
        try:
            # Basic implementation - could be enhanced with detailed explanations
            explanations = [
                "Ontology contains logical contradictions",
                "Possible causes:",
                "- Disjoint classes with common instances",
                "- Property domain/range violations", 
                "- Cardinality constraint violations",
                "- Unsatisfiable class definitions"
            ]
            
            # Try to identify specific issues
            unsatisfiable = self.get_unsatisfiable_classes(ontology)
            if unsatisfiable:
                explanations.append(f"Found {len(unsatisfiable)} unsatisfiable classes:")
                explanations.extend([f"  - {cls}" for cls in list(unsatisfiable)[:5]])
            
            return explanations
            
        except Exception as e:
            return [f"Failed to generate explanation: {str(e)}"]
