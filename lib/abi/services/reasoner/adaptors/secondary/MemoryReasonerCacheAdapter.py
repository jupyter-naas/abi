from abi.services.reasoner.ReasonerPorts import IReasonerCachePort, ReasoningConfiguration, ReasoningResult
from typing import Optional, Dict, Any
import time
import threading
from collections import OrderedDict
from abi import logger


class MemoryReasonerCacheAdapter(IReasonerCachePort):
    """
    In-memory cache adapter for reasoning results.
    
    This adapter provides fast, thread-safe caching of reasoning results using
    an LRU (Least Recently Used) eviction policy. It's suitable for development
    and moderate-scale production use where cache persistence is not required.
    
    Features:
    - Thread-safe operations
    - LRU eviction policy
    - Configurable cache size and TTL
    - Cache statistics and monitoring
    - Memory-efficient storage
    """
    
    def __init__(self, 
                 max_size: int = 1000,
                 ttl_seconds: int = 3600,
                 cleanup_interval: int = 300):
        """Initialize the memory cache adapter.
        
        Args:
            max_size: Maximum number of cached results
            ttl_seconds: Time-to-live for cached results in seconds
            cleanup_interval: Interval for cleanup of expired entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        
        # Thread-safe cache storage
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expired": 0,
            "total_requests": 0
        }
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"MemoryReasonerCacheAdapter initialized: max_size={max_size}, ttl={ttl_seconds}s")
    
    def _generate_cache_key(self, ontology_hash: str, config: ReasoningConfiguration) -> str:
        """Generate a unique cache key for the given parameters."""
        config_str = f"{config.reasoning_type.value}_{config.profile}_{config.timeout_seconds}"
        return f"{ontology_hash}_{config_str}"
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if a cache entry has expired."""
        return time.time() - entry["timestamp"] > self.ttl_seconds
    
    def _cleanup_expired(self):
        """Background thread to cleanup expired cache entries."""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                self._perform_cleanup()
            except Exception as e:
                logger.error(f"Cache cleanup error: {str(e)}")
    
    def _perform_cleanup(self):
        """Remove expired entries from cache."""
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                self._stats["expired"] += 1
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _evict_lru(self):
        """Evict least recently used entries to maintain cache size."""
        while len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats["evictions"] += 1
    
    def get_cached_result(self, 
                         ontology_hash: str, 
                         config: ReasoningConfiguration) -> Optional[ReasoningResult]:
        """Retrieve cached reasoning result."""
        cache_key = self._generate_cache_key(ontology_hash, config)
        
        with self._lock:
            self._stats["total_requests"] += 1
            
            if cache_key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            entry = self._cache[cache_key]
            
            # Check if expired
            if self._is_expired(entry):
                del self._cache[cache_key]
                self._stats["expired"] += 1
                self._stats["misses"] += 1
                return None
            
            # Move to end (mark as recently used)
            self._cache.move_to_end(cache_key)
            self._stats["hits"] += 1
            
            logger.debug(f"Cache hit for key: {cache_key}")
            return entry["result"]
    
    def cache_result(self, 
                    ontology_hash: str, 
                    config: ReasoningConfiguration, 
                    result: ReasoningResult) -> bool:
        """Cache a reasoning result."""
        cache_key = self._generate_cache_key(ontology_hash, config)
        
        try:
            with self._lock:
                # Evict LRU entries if necessary
                self._evict_lru()
                
                # Store the result
                entry = {
                    "result": result,
                    "timestamp": time.time(),
                    "ontology_hash": ontology_hash,
                    "config": config
                }
                
                self._cache[cache_key] = entry
                
                logger.debug(f"Cached result for key: {cache_key}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cache result: {str(e)}")
            return False
    
    def invalidate_cache(self, pattern: Optional[str] = None) -> bool:
        """Invalidate cached results."""
        try:
            with self._lock:
                if pattern is None:
                    # Clear entire cache
                    cleared_count = len(self._cache)
                    self._cache.clear()
                    logger.info(f"Cleared entire cache: {cleared_count} entries")
                else:
                    # Clear entries matching pattern
                    keys_to_remove = [key for key in self._cache.keys() if pattern in key]
                    for key in keys_to_remove:
                        del self._cache[key]
                    logger.info(f"Cleared {len(keys_to_remove)} cache entries matching pattern: {pattern}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {str(e)}")
            return False
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        with self._lock:
            total_requests = self._stats["total_requests"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate_percent": hit_rate,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "expired": self._stats["expired"],
                "total_requests": total_requests,
                "memory_usage_estimate": len(self._cache) * 1024,  # Rough estimate in bytes
                "ttl_seconds": self.ttl_seconds
            }
    
    def optimize_cache(self) -> Dict[str, Any]:
        """Perform cache optimization and return statistics."""
        with self._lock:
            initial_size = len(self._cache)
            
            # Remove expired entries
            self._perform_cleanup()
            
            # Compact cache if needed
            if len(self._cache) > self.max_size * 0.8:
                # Remove oldest 20% of entries
                remove_count = int(len(self._cache) * 0.2)
                keys_to_remove = list(self._cache.keys())[:remove_count]
                for key in keys_to_remove:
                    del self._cache[key]
                    self._stats["evictions"] += 1
            
            final_size = len(self._cache)
            
            result = {
                "initial_size": initial_size,
                "final_size": final_size,
                "removed_entries": initial_size - final_size,
                "optimization_successful": True
            }
            
            logger.info(f"Cache optimization completed: removed {result['removed_entries']} entries")
            return result
    
    def __len__(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._lock:
            return key in self._cache
