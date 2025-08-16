from abc import ABC, abstractmethod
from rdflib import Graph
from enum import Enum
from typing import Optional, Dict, List, Set, Any
from dataclasses import dataclass


class ReasoningType(Enum):
    """Types of reasoning operations supported by the reasoner service."""
    CONSISTENCY_CHECK = "consistency_check"
    CLASSIFICATION = "classification"
    INSTANCE_REALIZATION = "instance_realization"
    PROPERTY_ASSERTION = "property_assertion"
    SUBSUMPTION = "subsumption"
    FULL_INFERENCE = "full_inference"


class InconsistencyType(Enum):
    """Types of inconsistencies that can be detected."""
    CLASS_DISJOINTNESS = "class_disjointness"
    PROPERTY_DOMAIN_RANGE = "property_domain_range"
    CARDINALITY_VIOLATION = "cardinality_violation"
    UNSATISFIABLE_CLASS = "unsatisfiable_class"
    LOGICAL_CONTRADICTION = "logical_contradiction"


@dataclass
class ReasoningResult:
    """Container for reasoning operation results."""
    inferred_graph: Graph
    is_consistent: bool
    reasoning_time: float
    inconsistencies: List[InconsistencyType]
    warnings: List[str]
    metadata: Dict[str, Any]


@dataclass
class ReasoningConfiguration:
    """Configuration for reasoning operations."""
    reasoning_type: ReasoningType
    timeout_seconds: Optional[int] = 300
    cache_enabled: bool = True
    explain_inconsistencies: bool = True
    profile: str = "OWL2_DL"  # OWL2_DL, OWL2_EL, OWL2_QL, OWL2_RL
    incremental: bool = False


class IReasonerPort(ABC):
    """Secondary port for reasoner implementations."""
    
    @abstractmethod
    def initialize(self, base_ontology: Graph) -> bool:
        """Initialize the reasoner with a base ontology.
        
        Args:
            base_ontology: The base ontology graph to reason over
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def reason(self, 
               ontology: Graph, 
               config: ReasoningConfiguration) -> ReasoningResult:
        """Perform reasoning on the given ontology.
        
        Args:
            ontology: The ontology graph to reason over
            config: Configuration for the reasoning operation
            
        Returns:
            ReasoningResult: Complete results of the reasoning operation
        """
        pass
    
    @abstractmethod
    def check_consistency(self, ontology: Graph) -> bool:
        """Check if the ontology is logically consistent.
        
        Args:
            ontology: The ontology graph to check
            
        Returns:
            bool: True if consistent, False otherwise
        """
        pass
    
    @abstractmethod
    def get_unsatisfiable_classes(self, ontology: Graph) -> Set[str]:
        """Get classes that are unsatisfiable (equivalent to Nothing).
        
        Args:
            ontology: The ontology graph to analyze
            
        Returns:
            Set[str]: URIs of unsatisfiable classes
        """
        pass
    
    @abstractmethod
    def infer_class_hierarchy(self, ontology: Graph) -> Graph:
        """Infer the complete class hierarchy including implicit subclass relations.
        
        Args:
            ontology: The ontology graph to analyze
            
        Returns:
            Graph: Graph containing inferred subclass relations
        """
        pass
    
    @abstractmethod
    def classify_individuals(self, ontology: Graph) -> Graph:
        """Classify individuals to their most specific classes.
        
        Args:
            ontology: The ontology graph containing individuals
            
        Returns:
            Graph: Graph with inferred type assertions
        """
        pass
    
    @abstractmethod
    def explain_inconsistency(self, ontology: Graph) -> List[str]:
        """Provide explanations for why the ontology is inconsistent.
        
        Args:
            ontology: The inconsistent ontology graph
            
        Returns:
            List[str]: Human-readable explanations of inconsistencies
        """
        pass


class IReasonerService(ABC):
    """Primary port for the reasoner service."""
    
    @abstractmethod
    def infer_triples(self, 
                     graph: Graph, 
                     reasoning_type: ReasoningType = ReasoningType.FULL_INFERENCE) -> Graph:
        """Infer new triples from the given graph.
        
        Args:
            graph: The input graph to reason over
            reasoning_type: Type of reasoning to perform
            
        Returns:
            Graph: Graph containing original triples plus inferred triples
        """
        pass
    
    @abstractmethod
    def check_consistency(self, graph: Graph) -> bool:
        """Check if the graph is logically consistent.
        
        Args:
            graph: The graph to check for consistency
            
        Returns:
            bool: True if consistent, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_ontology(self, graph: Graph) -> ReasoningResult:
        """Perform comprehensive validation of an ontology.
        
        Args:
            graph: The ontology graph to validate
            
        Returns:
            ReasoningResult: Complete validation results
        """
        pass
    
    @abstractmethod
    def get_entailments(self, 
                       graph: Graph, 
                       query_pattern: str) -> Graph:
        """Get entailments matching a specific query pattern.
        
        Args:
            graph: The graph to query
            query_pattern: SPARQL pattern to match against entailments
            
        Returns:
            Graph: Graph containing matching entailments
        """
        pass
    
    @abstractmethod
    def explain_inference(self, 
                         graph: Graph, 
                         triple: tuple) -> List[str]:
        """Explain why a specific triple was inferred.
        
        Args:
            graph: The graph containing the inference
            triple: The triple (subject, predicate, object) to explain
            
        Returns:
            List[str]: Step-by-step explanation of the inference
        """
        pass
    
    @abstractmethod
    def get_reasoning_statistics(self) -> Dict[str, Any]:
        """Get statistics about reasoning operations.
        
        Returns:
            Dict[str, any]: Statistics including cache hits, reasoning times, etc.
        """
        pass


class IReasonerCachePort(ABC):
    """Port for caching reasoning results."""
    
    @abstractmethod
    def get_cached_result(self, ontology_hash: str, config: ReasoningConfiguration) -> Optional[ReasoningResult]:
        """Retrieve cached reasoning result.
        
        Args:
            ontology_hash: Hash of the ontology content
            config: Reasoning configuration used
            
        Returns:
            Optional[ReasoningResult]: Cached result if available, None otherwise
        """
        pass
    
    @abstractmethod
    def cache_result(self, 
                    ontology_hash: str, 
                    config: ReasoningConfiguration, 
                    result: ReasoningResult) -> bool:
        """Cache a reasoning result.
        
        Args:
            ontology_hash: Hash of the ontology content
            config: Reasoning configuration used
            result: Result to cache
            
        Returns:
            bool: True if caching successful, False otherwise
        """
        pass
    
    @abstractmethod
    def invalidate_cache(self, pattern: Optional[str] = None) -> bool:
        """Invalidate cached results.
        
        Args:
            pattern: Optional pattern to match for selective invalidation
            
        Returns:
            bool: True if invalidation successful, False otherwise
        """
        pass
