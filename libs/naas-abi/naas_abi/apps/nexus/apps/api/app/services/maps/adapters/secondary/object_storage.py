"""Maps objects read through the ABI engine's object storage (MinIO / S3 / filesystem).

Layer data is small (hundreds of KB) and changes only when it is published, so
each object is kept in the engine cache's hot tier for a minute (``MapsCache``):
a map load reads each object once instead of once per layer and member.
"""

from __future__ import annotations

import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import (
    MapsObjectMissingError,
    MapsObjectStorePort,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.storage_keys import split_key
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

OBJECT_TTL = datetime.timedelta(seconds=60)
# Larger objects are read from storage every time rather than held in Redis.
MAX_CACHED_BYTES = 8 * 1024 * 1024


class ObjectStorageMapsObjects(MapsObjectStorePort):
    def __init__(self, storage: Any, cache: MapsCache | None = None):
        self._storage = storage
        self._cache = cache or MapsCache(None)

    def read(self, key: str) -> bytes:
        cache_key = f"nexus:maps:object:{key}"
        cached = self._cache.get_binary(cache_key, OBJECT_TTL)
        if cached is not None:
            return cached
        prefix, name = split_key(key)
        try:
            content = self._storage.get_object(prefix, name)
        except Exceptions.ObjectNotFound as exc:
            raise MapsObjectMissingError(key) from exc
        if len(content) <= MAX_CACHED_BYTES:
            self._cache.set_binary(cache_key, content)
        return content
