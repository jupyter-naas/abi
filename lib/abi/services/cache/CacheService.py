from lib.abi.services.cache.CachePort import ICacheService, ICacheAdapter, CachedData, DataType, CacheNotFoundError, CacheExpiredError
from typing import Any, Callable
import datetime
import json
import pickle
import base64
import inspect
from collections import OrderedDict
from abi import logger

class ForceRefresh(Exception):
    pass

class CacheService(ICacheService):
    def __init__(self, adapter: ICacheAdapter):
        self.adapter = adapter
        
        self.deserializers = {
            DataType.TEXT: self.__get_text,
            DataType.JSON: self.__get_json,
            DataType.BINARY: self.__get_binary,
            DataType.PICKLE: self.__get_pickle
        }
    
    def __call__(self, key_builder: Callable, cache_type: DataType, ttl: datetime.timedelta | None = None, auto_cache: bool = True):
        """
        Decorator to cache function results.
        
        Args:
            key_builder: Function that takes the same parameters as the decorated function
                        and returns a cache key (string or dict)
            cache_type: Cache type to use (TEXT, JSON, BINARY, PICKLE). 
                       Required when auto_cache=True (default: None)
            ttl: Time-to-live for cached data. If specified, cached data will expire 
                 after this duration (default: None)
            auto_cache: Whether to automatically cache the result (default: True)
        
        Example:
            >>> # Create cache service instance
            >>> cache_service = CacheService(adapter)
            >>> 
            >>> # Apply cache decorator with explicit cache type
            >>> @cache_service(lambda user_id, include_profile=False: f"user_{user_id}_profile_{include_profile}", 
            ...                 cache_type=DataType.JSON)
            ... def get_user_data(user_id: int, include_profile: bool = False):
            ...     # Expensive operation (e.g., database query, API call)
            ...     return {"id": user_id, "name": "John Doe", "profile": include_profile}
            >>> 
            >>> # Disable auto-caching (only retrieves from cache, doesn't store)
            >>> @cache_service(lambda x: f"key_{x}", cache_type=DataType.TEXT, auto_cache=False)
            ... def get_data_no_auto_cache(x):
            ...     return f"data_{x}"
            >>> 
            >>> # Cache text data explicitly
            >>> @cache_service(lambda x: f"key_{x}", cache_type=DataType.TEXT)
            ... def get_text_data(x):
            ...     return f"data_{x}"
            >>> 
            >>> # Cache with TTL (expires after 1 hour)
            >>> @cache_service(lambda x: f"key_{x}", cache_type=DataType.JSON, 
            ...                 ttl=datetime.timedelta(hours=1))
            ... def get_data_with_ttl(x):
            ...     return {"data": x, "timestamp": datetime.datetime.now()}
            >>> 
            >>> # Force cache refresh with special parameter
            >>> result = get_user_data(123, True, force_cache_refresh=True)  # Bypasses cache
            >>> 
            >>> # First call - executes function and caches result
            >>> result1 = get_user_data(123, True)  # Cache key: "user_123_profile_True"
            >>> 
            >>> # Second call - returns cached result
            >>> result2 = get_user_data(123, True)  # Returns from cache
        """
        
        logger.debug(f"Cache decorator called with key_builder: {key_builder}, auto_cache: {auto_cache}, cache_type: {cache_type}, ttl: {ttl}")
        def decorator(func):
            def wrapper(*args, **kwargs):
                
                # Step 1: Create a complete mapping of all function arguments
                # This will contain all arguments passed to the decorated function,
                # including positional args, keyword args, and default values
                mapped_args = OrderedDict()
                func_args = inspect.signature(func).parameters
                func_args_list = list(func_args.keys())
                
                # Step 2: Map positional arguments to their parameter names
                # Convert positional args like func(a, b, c) to named args like {'x': a, 'y': b, 'z': c}
                for arg_index in range(len(args)):
                    arg_name = func_args_list[arg_index]
                    mapped_args[arg_name] = args[arg_index]
                    
                # Step 3: Add keyword arguments to the mapping
                # Only include kwargs that are actually parameters of the decorated function
                for arg_name, arg_value in kwargs.items():
                    if arg_name in func_args_list:
                        mapped_args[arg_name] = arg_value
                         
                # Step 4: Fill in default values for parameters that weren't provided
                # This ensures we have a complete picture of all function arguments
                for arg_name, arg_value in func_args.items():
                    if arg_value.default is not arg_value.empty and arg_name not in mapped_args:
                        mapped_args[arg_name] = arg_value.default
                
                # Step 5: Filter arguments to only include those needed by the key_builder
                # The key_builder function may only need a subset of the decorated function's arguments
                key_builder_args = inspect.signature(key_builder).parameters
                filtered_args = OrderedDict()
                
                # Only pass arguments that the key_builder function expects
                for arg_name, arg_value in mapped_args.items():
                    if arg_name in key_builder_args:
                        filtered_args[arg_name] = arg_value

                # Build cache key using the provided key_builder function
                cache_key = key_builder(**filtered_args)
                
                # Try to get from cache first
                try:
                    if 'force_cache_refresh' in kwargs:
                        del kwargs['force_cache_refresh']
                        raise ForceRefresh()
                    
                    cached_data = self.__get_cached_data(cache_key, ttl)
                    
                    if cached_data.data_type == cache_type:
                        return self.deserializers[cache_type](cached_data)
                    else:
                        raise CacheNotFoundError(f"Cache Data Type change from {cached_data.data_type} to {cache_type}.")
                    
                except (CacheNotFoundError, CacheExpiredError, ForceRefresh):
                    # If not in cache or expired, execute function
                    result = func(*args, **kwargs)
                    
                    # Cache result if auto_cache is enabled
                    if auto_cache:
                        # Use specified cache_type
                        if cache_type == DataType.TEXT:
                            self.set_text(cache_key, result)
                        elif cache_type == DataType.JSON:
                            self.set_json(cache_key, result)
                        elif cache_type == DataType.BINARY:
                            self.set_binary(cache_key, result)
                        elif cache_type == DataType.PICKLE:
                            self.set_pickle(cache_key, result)
                        else:
                            # Require explicit cache type specification
                            raise ValueError(
                                f"cache_type must be explicitly specified. "
                                f"Result type: {type(result).__name__}. "
                                f"Available types: {[dt.name for dt in DataType]}"
                                f"Cache key: {cache_key}"
                                f"cache_type: {cache_type}"
                            )
                    
                    return result
            
            return wrapper
        return decorator
    
    def __get_cached_data(self, key: str, ttl: datetime.timedelta | None = None) -> CachedData: 
        try:
            cached_data = self.adapter.get(key)
        except (CacheNotFoundError, Exception) as _ :
            raise CacheNotFoundError(f"Cache not found: {key}")
        
        if ttl and datetime.datetime.fromisoformat(cached_data.created_at) + ttl < datetime.datetime.now():
            raise CacheExpiredError(f"Cache expired: {key}. TTL: {ttl}. Created at: {cached_data.created_at}.")
        
        return cached_data
    
    def get(self, key: str, ttl: datetime.timedelta | None = None) -> Any:
        cached_data = self.__get_cached_data(key, ttl)
        return self.deserializers[cached_data.data_type](cached_data)
    
    def __get_text(self, data: CachedData) -> str:
        return data.data
    
    def __get_json(self, data: CachedData) -> dict:
        return json.loads(data.data)
    
    def __get_binary(self, data: CachedData) -> bytes:
        return base64.b64decode(data.data)
    
    def __get_pickle(self, data: CachedData) -> Any:
        return pickle.loads(base64.b64decode(data.data))
    
    def set_text(self, key: str, value: str) -> None:
        assert isinstance(value, str), f"Value must be a string. Got {type(value)}"
        cached_data = CachedData(key=key, data=value, data_type=DataType.TEXT)
        self.adapter.set(key, cached_data)
    
    def set_json(self, key: str, value: Any) -> None:
        cached_data = CachedData(key=key, data=json.dumps(value), data_type=DataType.JSON)
        self.adapter.set(key, cached_data)
    
    def set_binary(self, key: str, value: bytes) -> None:
        assert isinstance(value, bytes), f"Value must be a bytes. Got {type(value)}"
        cached_data = CachedData(key=key, data=base64.b64encode(value).decode(), data_type=DataType.BINARY)
        self.adapter.set(key, cached_data)

    def set_pickle(self, key: str, value: Any) -> None:
        cached_data = CachedData(key=key, data=base64.b64encode(pickle.dumps(value)).decode(), data_type=DataType.PICKLE)
        self.adapter.set(key, cached_data)
    
    def exists(self, key: str) -> bool:
        return self.adapter.exists(key)