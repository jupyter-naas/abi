from abi.services.reasoner.ReasonerService import ReasonerService
from abi.services.reasoner.ReasonerPorts import IReasonerPort, IReasonerCachePort
from abi.services.reasoner.adaptors.secondary.Owlready2ReasonerAdapter import Owlready2ReasonerAdapter
from typing import Optional, Dict, Any
from abi import logger


class ReasonerFactory:
    """
    Factory for creating reasoner service instances with appropriate configurations.
    
    This factory handles the complexity of setting up reasoner services with
    different backends, cache configurations, and performance optimizations
    based on the specific use case and ontology characteristics.
    
    Supported Reasoners:
    - Owlready2 (with HermiT/Pellet backends)
    - Future: FaCT++, ELK, custom implementations
    """
    
    @staticmethod
    def create_reasoner_service(
        reasoner_type: str = "owlready2",
        cache_enabled: bool = True,
        configuration: Optional[Dict[str, Any]] = None
    ) -> ReasonerService:
        """Create a configured reasoner service.
        
        Args:
            reasoner_type: Type of reasoner backend to use
            cache_enabled: Whether to enable result caching
            configuration: Additional configuration options
            
        Returns:
            ReasonerService: Configured reasoner service instance
            
        Raises:
            ValueError: If reasoner type is not supported
            ImportError: If required dependencies are missing
        """
        config = configuration or {}
        
        # Create reasoner port based on type
        reasoner_port = ReasonerFactory._create_reasoner_port(reasoner_type, config)
        
        # Create cache port if enabled
        cache_port = None
        if cache_enabled:
            cache_port = ReasonerFactory._create_cache_port(config.get("cache_type", "memory"))
        
        # Get timeout configuration
        default_timeout = config.get("timeout_seconds", 300)
        
        service = ReasonerService(
            reasoner_port=reasoner_port,
            cache_port=cache_port,
            default_timeout=default_timeout
        )
        
        logger.info(f"Created reasoner service with {reasoner_type} backend, "
                   f"cache {'enabled' if cache_enabled else 'disabled'}")
        
        return service
    
    @staticmethod
    def _create_reasoner_port(reasoner_type: str, config: Dict[str, Any]) -> IReasonerPort:
        """Create a reasoner port based on the specified type."""
        reasoner_type = reasoner_type.lower()
        
        if reasoner_type == "owlready2":
            sub_reasoner = config.get("sub_reasoner", "hermit")
            java_memory = config.get("java_memory", "2G")
            return Owlready2ReasonerAdapter(
                reasoner_type=sub_reasoner,
                java_memory=java_memory
            )
        
        elif reasoner_type == "jena":
            # Future implementation
            raise NotImplementedError("Jena reasoner adapter not yet implemented")
        
        elif reasoner_type == "elk":
            # Future implementation
            raise NotImplementedError("ELK reasoner adapter not yet implemented")
        
        elif reasoner_type == "fact++":
            # Future implementation
            raise NotImplementedError("FaCT++ reasoner adapter not yet implemented")
        
        else:
            raise ValueError(f"Unsupported reasoner type: {reasoner_type}")
    
    @staticmethod
    def _create_cache_port(cache_type: str) -> Optional[IReasonerCachePort]:
        """Create a cache port based on the specified type."""
        if cache_type == "memory":
            # Import here to avoid circular dependencies
            from abi.services.reasoner.adaptors.secondary.MemoryReasonerCacheAdapter import MemoryReasonerCacheAdapter
            return MemoryReasonerCacheAdapter()
        
        elif cache_type == "redis":
            # Future implementation - Redis cache adapter
            # from abi.services.reasoner.adaptors.secondary.RedisReasonerCacheAdapter import RedisReasonerCacheAdapter
            # return RedisReasonerCacheAdapter()
            logger.warning("Redis cache not yet implemented, falling back to memory cache")
            from abi.services.reasoner.adaptors.secondary.MemoryReasonerCacheAdapter import MemoryReasonerCacheAdapter
            return MemoryReasonerCacheAdapter()
        
        elif cache_type == "file":
            # Future implementation - File cache adapter
            # from abi.services.reasoner.adaptors.secondary.FileReasonerCacheAdapter import FileReasonerCacheAdapter
            # return FileReasonerCacheAdapter()
            logger.warning("File cache not yet implemented, falling back to memory cache")
            from abi.services.reasoner.adaptors.secondary.MemoryReasonerCacheAdapter import MemoryReasonerCacheAdapter
            return MemoryReasonerCacheAdapter()
        
        else:
            logger.warning(f"Unknown cache type: {cache_type}, disabling cache")
            return None
    
    @staticmethod
    def create_bfo_optimized_reasoner(
        performance_profile: str = "balanced",
        ontology_size: str = "medium"
    ) -> ReasonerService:
        """Create a reasoner service optimized for BFO-based ontologies.
        
        Args:
            performance_profile: "fast", "balanced", or "comprehensive"
            ontology_size: "small", "medium", "large", or "enterprise"
            
        Returns:
            ReasonerService: Optimized reasoner service for BFO ontologies
        """
        # Determine optimal configuration based on profiles
        if performance_profile == "fast":
            config = {
                "sub_reasoner": "hermit",  # Faster than Pellet for most cases
                "java_memory": "1G",
                "timeout_seconds": 60,
                "cache_type": "memory"
            }
        elif performance_profile == "balanced":
            config = {
                "sub_reasoner": "hermit",
                "java_memory": "2G",
                "timeout_seconds": 300,
                "cache_type": "memory"
            }
        else:  # comprehensive
            config = {
                "sub_reasoner": "pellet",  # More comprehensive reasoning
                "java_memory": "4G",
                "timeout_seconds": 600,
                "cache_type": "memory"
            }
        
        # Adjust for ontology size
        if ontology_size == "large":
            config["java_memory"] = "4G"
            config["timeout_seconds"] = config["timeout_seconds"] * 2
        elif ontology_size == "enterprise":
            config["java_memory"] = "8G"
            config["timeout_seconds"] = config["timeout_seconds"] * 3
            config["cache_type"] = "redis"  # Use persistent cache for large ontologies
        
        return ReasonerFactory.create_reasoner_service(
            reasoner_type="owlready2",
            cache_enabled=True,
            configuration=config
        )
    
    @staticmethod
    def create_development_reasoner() -> ReasonerService:
        """Create a lightweight reasoner service for development and testing."""
        config = {
            "sub_reasoner": "hermit",
            "java_memory": "512M",
            "timeout_seconds": 30,
            "cache_type": "memory"
        }
        
        return ReasonerFactory.create_reasoner_service(
            reasoner_type="owlready2",
            cache_enabled=True,
            configuration=config
        )
    
    @staticmethod
    def get_supported_reasoners() -> Dict[str, Dict[str, Any]]:
        """Get information about supported reasoner backends."""
        return {
            "owlready2": {
                "description": "Python-based OWL reasoner using HermiT or Pellet",
                "profiles": ["OWL2_DL", "OWL2_EL", "OWL2_QL"],
                "features": ["consistency_checking", "classification", "instance_realization"],
                "requirements": ["owlready2", "java_runtime"],
                "performance": "good",
                "recommended_for": ["BFO_ontologies", "medium_scale", "development"]
            },
            "jena": {
                "description": "Apache Jena reasoning framework",
                "profiles": ["OWL2_DL", "RDFS", "OWL_Lite"],
                "features": ["rule_based_reasoning", "custom_rules"],
                "requirements": ["py4j", "java_runtime", "jena"],
                "performance": "excellent",
                "status": "planned"
            },
            "elk": {
                "description": "High-performance EL reasoner",
                "profiles": ["OWL2_EL"],
                "features": ["classification", "subsumption"],
                "requirements": ["elk_reasoner", "java_runtime"],
                "performance": "excellent",
                "recommended_for": ["large_scale", "EL_ontologies"],
                "status": "planned"
            }
        }
