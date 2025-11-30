from pydantic import BaseModel, Field
import datetime
from enum import Enum
from typing import Any

class CacheNotFoundError(Exception):
    pass

class CacheExpiredError(Exception):
    pass

class DataType(str, Enum):
    TEXT = "text"
    JSON = "json"
    BINARY = "binary"
    PICKLE = "pickle"

class CachedData(BaseModel):
    key: str
    data: Any
    data_type: DataType
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

class ICacheAdapter:
    
    def get(self, key: str) -> CachedData:
        raise NotImplementedError("Not implemented")
    
    def set(self, key: str, value: CachedData) -> None:
        raise NotImplementedError("Not implemented")
    
    def delete(self, key: str) -> None:
        raise NotImplementedError("Not implemented")
    
    def exists(self, key: str) -> bool:
        raise NotImplementedError("Not implemented")

class ICacheService:
    
    adapter: ICacheAdapter
    
    def __init__(self, adapter: ICacheAdapter):
        self.adapter = adapter
    
    def exists(self, key: str) -> bool:
        raise NotImplementedError("Not implemented")
    
    def get(self, key: str, ttl: datetime.timedelta | None = None) -> Any:
        raise NotImplementedError("Not implemented")
    
    def set_text(self, key: str, value: str) -> None:
        raise NotImplementedError("Not implemented")
    
    def set_json(self, key: str, value: dict) -> None:
        raise NotImplementedError("Not implemented")
    
    def set_binary(self, key: str, value: bytes) -> None:
        raise NotImplementedError("Not implemented")

    def set_pickle(self, key: str, value: Any) -> None:
        raise NotImplementedError("Not implemented")
    
        