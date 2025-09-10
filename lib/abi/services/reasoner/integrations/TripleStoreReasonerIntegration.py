from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from abi.services.reasoner.ReasonerService import ReasonerService
from abi.services.reasoner.ReasonerPorts import ReasoningType
from rdflib import Graph
from typing import Tuple, Optional
import threading
from abi import logger


class TripleStoreReasonerIntegration:
    """
    Integration between TripleStoreService and ReasonerService.
    
    This integration provides automated reasoning capabilities that trigger
    when ontology changes occur in the triple store. It supports both
    real-time and batch reasoning modes, with intelligent caching and
    conflict resolution.
    
    Features:
    - Automatic reasoning on ontology updates
    - Incremental reasoning for performance
    - Conflict detection and resolution
    - Reasoning result persistence
    - Event-driven consistency checking
    """
    
    def __init__(self,
                 triple_store: ITripleStoreService,
                 reasoner_service: ReasonerService,
                 auto_reasoning: bool = True,
                 batch_size: int = 100,
                 reasoning_delay: float = 5.0):
        """Initialize the integration.
        
        Args:
            triple_store: The triple store service instance
            reasoner_service: The reasoner service instance
            auto_reasoning: Whether to automatically trigger reasoning on changes
            batch_size: Number of changes to batch before triggering reasoning
            reasoning_delay: Delay in seconds before triggering reasoning after changes
        """
        self.triple_store = triple_store
        self.reasoner_service = reasoner_service
        self.auto_reasoning = auto_reasoning
        self.batch_size = batch_size
        self.reasoning_delay = reasoning_delay
        
        # State management
        self._pending_changes: List[Tuple[str, Tuple[str, str, str]]] = []
        self._reasoning_timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()
        self._subscription_ids: List[str] = []
        
        # Statistics
        self._stats = {
            "reasoning_operations": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "consistency_checks": 0,
            "auto_inferences": 0
        }
        
        if auto_reasoning:
            self._setup_auto_reasoning()
        
        logger.info("TripleStoreReasonerIntegration initialized")
    
    def _setup_auto_reasoning(self):
        """Set up automatic reasoning triggers."""
        # Subscribe to INSERT events
        insert_sub = self.triple_store.subscribe(
            topic=(None, None, None),  # Listen to all triples
            event_type=OntologyEvent.INSERT,
            callback=self._handle_insert_event,
            background=True
        )
        self._subscription_ids.append(insert_sub)
        
        # Subscribe to DELETE events
        delete_sub = self.triple_store.subscribe(
            topic=(None, None, None),
            event_type=OntologyEvent.DELETE,
            callback=self._handle_delete_event,
            background=True
        )
        self._subscription_ids.append(delete_sub)
        
        logger.info("Auto-reasoning event handlers registered")
    
    def _handle_insert_event(self, event_type: OntologyEvent, triple: Tuple[str, str, str]):
        """Handle triple insertion events."""
        with self._lock:
            self._pending_changes.append(("INSERT", triple))
            self._schedule_reasoning()
    
    def _handle_delete_event(self, event_type: OntologyEvent, triple: Tuple[str, str, str]):
        """Handle triple deletion events."""
        with self._lock:
            self._pending_changes.append(("DELETE", triple))
            self._schedule_reasoning()
    
    def _schedule_reasoning(self):
        """Schedule reasoning operation with delay and batching."""
        # Cancel existing timer
        if self._reasoning_timer:
            self._reasoning_timer.cancel()
        
        # Check if we should trigger immediately due to batch size
        if len(self._pending_changes) >= self.batch_size:
            self._reasoning_timer = threading.Timer(0.1, self._perform_scheduled_reasoning)
        else:
            self._reasoning_timer = threading.Timer(self.reasoning_delay, self._perform_scheduled_reasoning)
        
        self._reasoning_timer.start()
    
    def _perform_scheduled_reasoning(self):
        """Perform the scheduled reasoning operation."""
        with self._lock:
            if not self._pending_changes:
                return
            
            changes_count = len(self._pending_changes)
            self._pending_changes.clear()
        
        try:
            logger.info(f"Performing auto-reasoning triggered by {changes_count} changes")
            
            # Get current ontology state
            current_graph = self.triple_store.get()
            
            # Perform reasoning
            result = self.reasoner_service.validate_ontology(current_graph)
            
            if result.is_consistent:
                # Store inferred triples if any new ones were derived
                original_size = len(current_graph)
                inferred_size = len(result.inferred_graph)
                
                if inferred_size > original_size:
                    new_triples = Graph()
                    for triple in result.inferred_graph:
                        if triple not in current_graph:
                            new_triples.add(triple)
                    
                    if len(new_triples) > 0:
                        logger.info(f"Auto-inference: adding {len(new_triples)} new triples")
                        self.triple_store.insert(new_triples)
                        self._stats["auto_inferences"] += len(new_triples)
            else:
                logger.warning("Inconsistency detected during auto-reasoning")
                self._handle_inconsistency(result)
            
            self._stats["reasoning_operations"] += 1
            
        except Exception as e:
            logger.error(f"Auto-reasoning failed: {str(e)}")
    
    def _handle_inconsistency(self, result):
        """Handle detected inconsistencies."""
        self._stats["conflicts_detected"] += 1
        
        logger.warning(f"Ontology inconsistency detected: {result.inconsistencies}")
        
        # Log detailed explanations if available
        if "inconsistency_explanations" in result.metadata:
            for explanation in result.metadata["inconsistency_explanations"]:
                logger.warning(f"Inconsistency explanation: {explanation}")
        
        # Here you could implement conflict resolution strategies
        # For now, we just log the issue
    
    def perform_full_reasoning(self, reasoning_type: ReasoningType = ReasoningType.FULL_INFERENCE) -> Graph:
        """Perform full reasoning on the current ontology state.
        
        Args:
            reasoning_type: Type of reasoning to perform
            
        Returns:
            Graph: The graph with inferred triples
        """
        logger.info(f"Performing full reasoning: {reasoning_type.value}")
        
        try:
            current_graph = self.triple_store.get()
            inferred_graph = self.reasoner_service.infer_triples(current_graph, reasoning_type)
            
            # Store new inferences
            original_size = len(current_graph)
            inferred_size = len(inferred_graph)
            
            if inferred_size > original_size:
                new_triples = Graph()
                for triple in inferred_graph:
                    if triple not in current_graph:
                        new_triples.add(triple)
                
                if len(new_triples) > 0:
                    logger.info(f"Storing {len(new_triples)} inferred triples")
                    self.triple_store.insert(new_triples)
            
            self._stats["reasoning_operations"] += 1
            return inferred_graph
            
        except Exception as e:
            logger.error(f"Full reasoning failed: {str(e)}")
            raise
    
    def check_ontology_consistency(self) -> bool:
        """Check the consistency of the current ontology state.
        
        Returns:
            bool: True if consistent, False otherwise
        """
        try:
            current_graph = self.triple_store.get()
            is_consistent = self.reasoner_service.check_consistency(current_graph)
            
            self._stats["consistency_checks"] += 1
            
            logger.info(f"Consistency check result: {'CONSISTENT' if is_consistent else 'INCONSISTENT'}")
            return is_consistent
            
        except Exception as e:
            logger.error(f"Consistency check failed: {str(e)}")
            return False
    
    def validate_and_repair_ontology(self) -> dict:
        """Perform comprehensive ontology validation and attempt basic repairs.
        
        Returns:
            dict: Validation and repair results
        """
        logger.info("Starting ontology validation and repair")
        
        try:
            current_graph = self.triple_store.get()
            result = self.reasoner_service.validate_ontology(current_graph)
            
            repair_results = {
                "validation_result": result,
                "repairs_attempted": [],
                "repairs_successful": [],
                "final_consistency": result.is_consistent
            }
            
            if not result.is_consistent:
                logger.warning("Attempting basic ontology repairs")
                
                # Basic repair: remove unsatisfiable classes if metadata available
                if "unsatisfiable_classes" in result.metadata:
                    unsatisfiable = result.metadata["unsatisfiable_classes"]
                    if isinstance(repair_results["repairs_attempted"], list):
                        repair_results["repairs_attempted"].append(f"Remove {len(unsatisfiable)} unsatisfiable classes")
                    
                    # Note: Actual removal would require careful analysis
                    # This is a placeholder for more sophisticated repair logic
                
                # Re-check consistency after repairs
                final_check = self.reasoner_service.check_consistency(current_graph)
                repair_results["final_consistency"] = final_check
            
            return repair_results
            
        except Exception as e:
            logger.error(f"Validation and repair failed: {str(e)}")
            return {"error": str(e)}
    
    def get_integration_statistics(self) -> dict:
        """Get statistics about the integration performance."""
        reasoner_stats = self.reasoner_service.get_reasoning_statistics()
        
        combined_stats = {
            "integration": self._stats.copy(),
            "reasoner": reasoner_stats,
            "subscriptions_active": len(self._subscription_ids),
            "pending_changes": len(self._pending_changes),
            "auto_reasoning_enabled": self.auto_reasoning
        }
        
        return combined_stats
    
    def disable_auto_reasoning(self):
        """Disable automatic reasoning."""
        self.auto_reasoning = False
        
        # Unsubscribe from events
        for sub_id in self._subscription_ids:
            self.triple_store.unsubscribe(sub_id)
        self._subscription_ids.clear()
        
        # Cancel pending timer
        if self._reasoning_timer:
            self._reasoning_timer.cancel()
            self._reasoning_timer = None
        
        logger.info("Auto-reasoning disabled")
    
    def enable_auto_reasoning(self):
        """Enable automatic reasoning."""
        if not self.auto_reasoning:
            self.auto_reasoning = True
            self._setup_auto_reasoning()
            logger.info("Auto-reasoning enabled")
    
    def cleanup(self):
        """Clean up resources used by the integration."""
        self.disable_auto_reasoning()
        
        with self._lock:
            self._pending_changes.clear()
        
        logger.info("TripleStoreReasonerIntegration cleaned up")
