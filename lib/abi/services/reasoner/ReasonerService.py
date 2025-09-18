from abi.services.reasoner.ReasonerPorts import (
    IReasonerService,
    IReasonerPort,
    IReasonerCachePort,
    ReasoningType,
    ReasoningConfiguration,
    ReasoningResult
)
from rdflib import Graph
from typing import Optional, Dict, List, Any
import hashlib
import time
from abi import logger


class ReasonerService(IReasonerService):
    """
    ReasonerService provides OWL reasoning capabilities for ontologies.
    
    This service acts as a facade for ontology reasoning operations, providing
    consistency checking, classification, inference, and explanation capabilities
    while supporting multiple reasoner backends and caching for performance.
    
    Key Features:
    - Multiple reasoner backend support (Owlready2, HermiT, FaCT++, ELK)
    - Intelligent caching of reasoning results
    - Incremental reasoning for performance
    - Detailed inconsistency explanations
    - BFO-aware reasoning optimizations
    
    Example:
        >>> reasoner = ReasonerService(owlready2_adapter, cache_adapter)
        >>> result = reasoner.validate_ontology(my_ontology)
        >>> if not result.is_consistent:
        ...     print(f"Found {len(result.inconsistencies)} inconsistencies")
    """
    
    def __init__(self, 
                 reasoner_port: IReasonerPort,
                 cache_port: Optional[IReasonerCachePort] = None,
                 default_timeout: int = 300):
        """Initialize the reasoner service.
        
        Args:
            reasoner_port: The reasoner implementation to use
            cache_port: Optional cache implementation for performance
            default_timeout: Default timeout for reasoning operations in seconds
        """
        self.__reasoner_port = reasoner_port
        self.__cache_port = cache_port
        self.__default_timeout = default_timeout
        self.__statistics = {
            "total_operations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "average_reasoning_time": 0.0,
            "consistency_checks": 0,
            "inference_operations": 0,
            "failed_operations": 0
        }
        
        logger.info("ReasonerService initialized")
    
    def _compute_ontology_hash(self, graph: Graph) -> str:
        """Compute a hash of the ontology content for caching."""
        # Serialize graph to a consistent format for hashing
        serialized = graph.serialize(format='turtle')
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def _update_statistics(self, operation_type: str, reasoning_time: float, cache_hit: bool = False):
        """Update internal statistics."""
        self.__statistics["total_operations"] += 1
        
        if cache_hit:
            self.__statistics["cache_hits"] += 1
        else:
            self.__statistics["cache_misses"] += 1
        
        # Update average reasoning time
        total_ops = self.__statistics["total_operations"]
        current_avg = self.__statistics["average_reasoning_time"]
        self.__statistics["average_reasoning_time"] = (
            (current_avg * (total_ops - 1) + reasoning_time) / total_ops
        )
        
        if operation_type == "consistency":
            self.__statistics["consistency_checks"] += 1
        elif operation_type == "inference":
            self.__statistics["inference_operations"] += 1
    
    def infer_triples(self, 
                     graph: Graph, 
                     reasoning_type: ReasoningType = ReasoningType.FULL_INFERENCE) -> Graph:
        """Infer new triples from the given graph."""
        logger.info(f"Starting {reasoning_type.value} inference on graph with {len(graph)} triples")
        
        start_time = time.time()
        ontology_hash = self._compute_ontology_hash(graph)
        
        # Check cache if available
        if self.__cache_port:
            config = ReasoningConfiguration(reasoning_type=reasoning_type)
            cached_result = self.__cache_port.get_cached_result(ontology_hash, config)
            if cached_result:
                logger.info("Retrieved inference result from cache")
                self._update_statistics("inference", time.time() - start_time, cache_hit=True)
                return cached_result.inferred_graph
        
        try:
            # Perform reasoning
            config = ReasoningConfiguration(
                reasoning_type=reasoning_type,
                timeout_seconds=self.__default_timeout,
                cache_enabled=self.__cache_port is not None
            )
            
            result = self.__reasoner_port.reason(graph, config)
            
            # Cache result if caching is enabled
            if self.__cache_port and result.is_consistent:
                self.__cache_port.cache_result(ontology_hash, config, result)
            
            reasoning_time = time.time() - start_time
            self._update_statistics("inference", reasoning_time)
            
            logger.info(f"Inference completed in {reasoning_time:.2f}s, "
                       f"inferred {len(result.inferred_graph) - len(graph)} new triples")
            
            return result.inferred_graph
            
        except Exception as e:
            self.__statistics["failed_operations"] += 1
            logger.error(f"Inference failed: {str(e)}")
            raise
    
    def check_consistency(self, graph: Graph) -> bool:
        """Check if the graph is logically consistent."""
        logger.info(f"Checking consistency of graph with {len(graph)} triples")
        
        start_time = time.time()
        
        try:
            is_consistent = self.__reasoner_port.check_consistency(graph)
            
            reasoning_time = time.time() - start_time
            self._update_statistics("consistency", reasoning_time)
            
            logger.info(f"Consistency check completed in {reasoning_time:.2f}s: "
                       f"{'CONSISTENT' if is_consistent else 'INCONSISTENT'}")
            
            return is_consistent
            
        except Exception as e:
            self.__statistics["failed_operations"] += 1
            logger.error(f"Consistency check failed: {str(e)}")
            raise
    
    def validate_ontology(self, graph: Graph) -> ReasoningResult:
        """Perform comprehensive validation of an ontology."""
        logger.info(f"Starting comprehensive validation of ontology with {len(graph)} triples")
        
        start_time = time.time()
        ontology_hash = self._compute_ontology_hash(graph)
        
        # Check cache
        if self.__cache_port:
            config = ReasoningConfiguration(reasoning_type=ReasoningType.FULL_INFERENCE)
            cached_result = self.__cache_port.get_cached_result(ontology_hash, config)
            if cached_result:
                logger.info("Retrieved validation result from cache")
                return cached_result
        
        try:
            config = ReasoningConfiguration(
                reasoning_type=ReasoningType.FULL_INFERENCE,
                timeout_seconds=self.__default_timeout,
                explain_inconsistencies=True
            )
            
            result = self.__reasoner_port.reason(graph, config)
            
            # Add additional validation checks
            if not result.is_consistent:
                unsatisfiable_classes = self.__reasoner_port.get_unsatisfiable_classes(graph)
                result.metadata["unsatisfiable_classes"] = list(unsatisfiable_classes)
                
                explanations = self.__reasoner_port.explain_inconsistency(graph)
                result.metadata["inconsistency_explanations"] = explanations
            
            # Cache comprehensive result
            if self.__cache_port:
                self.__cache_port.cache_result(ontology_hash, config, result)
            
            reasoning_time = time.time() - start_time
            logger.info(f"Ontology validation completed in {reasoning_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.__statistics["failed_operations"] += 1
            logger.error(f"Ontology validation failed: {str(e)}")
            raise
    
    def get_entailments(self, graph: Graph, query_pattern: str) -> Graph:
        """Get entailments matching a specific query pattern."""
        logger.info(f"Getting entailments for pattern: {query_pattern}")
        
        start_time = time.time()
        
        try:
            # First infer all triples
            inferred_graph = self.infer_triples(graph)
            
            # Execute SPARQL query on inferred graph
            results = inferred_graph.query(query_pattern)
            
            # Create result graph
            result_graph = Graph()
            for result in results:
                # Handle different result types from SPARQL queries
                if hasattr(result, '__len__') and len(result) >= 3:
                    result_graph.add((result[0], result[1], result[2]))
            
            reasoning_time = time.time() - start_time
            logger.info(f"Entailment query completed in {reasoning_time:.2f}s, "
                       f"found {len(result_graph)} matching triples")
            
            return result_graph
            
        except Exception as e:
            logger.error(f"Entailment query failed: {str(e)}")
            raise
    
    def explain_inference(self, graph: Graph, triple: tuple) -> List[str]:
        """Explain why a specific triple was inferred."""
        logger.info(f"Explaining inference of triple: {triple}")
        
        try:
            # Check if the triple is actually inferred
            inferred_graph = self.infer_triples(graph)
            
            if triple not in inferred_graph:
                return ["Triple is not present in the inferred graph"]
            
            if triple in graph:
                return ["Triple is explicitly asserted in the original graph"]
            
            # For now, provide basic explanation
            # TODO: Implement detailed proof tree generation
            explanations = [
                f"Triple {triple} was inferred through reasoning",
                "Detailed proof tree generation not yet implemented"
            ]
            
            return explanations
            
        except Exception as e:
            logger.error(f"Inference explanation failed: {str(e)}")
            return [f"Error explaining inference: {str(e)}"]
    
    def get_reasoning_statistics(self) -> Dict[str, Any]:
        """Get statistics about reasoning operations."""
        cache_hit_rate = 0.0
        if self.__statistics["total_operations"] > 0:
            cache_hit_rate = (
                self.__statistics["cache_hits"] / self.__statistics["total_operations"]
            ) * 100
        
        stats = self.__statistics.copy()
        stats["cache_hit_rate_percent"] = cache_hit_rate
        stats["cache_enabled"] = self.__cache_port is not None
        
        return stats
    
    def invalidate_reasoning_cache(self, pattern: Optional[str] = None) -> bool:
        """Invalidate reasoning cache."""
        if not self.__cache_port:
            logger.warning("No cache port configured")
            return False
        
        try:
            result = self.__cache_port.invalidate_cache(pattern)
            logger.info(f"Cache invalidation {'successful' if result else 'failed'}")
            return result
        except Exception as e:
            logger.error(f"Cache invalidation failed: {str(e)}")
            return False
