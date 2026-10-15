from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.secondary.object_storage import (
    ObjectStorageMapsObjects,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import MapsObjectMissingError
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.CacheService import TIER_HOT, CacheService
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions


class _Storage:
    def __init__(self):
        self.objects = {("maps", "a.geojson"): b"A"}
        self.reads = 0

    def get_object(self, prefix: str, key: str) -> bytes:
        self.reads += 1
        if (prefix, key) not in self.objects:
            raise Exceptions.ObjectNotFound(key)
        return self.objects[(prefix, key)]


def _cache(tmp_path) -> MapsCache:
    return MapsCache(CacheService(adapters=[(TIER_HOT, CacheFSAdapter(str(tmp_path)))]))


def test_objects_are_read_once_while_cached(tmp_path) -> None:
    storage = _Storage()
    objects = ObjectStorageMapsObjects(storage, _cache(tmp_path))
    assert objects.read("maps/a.geojson") == b"A"
    assert objects.read("maps/a.geojson") == b"A"
    assert storage.reads == 1


def test_missing_objects_are_not_cached(tmp_path) -> None:
    storage = _Storage()
    objects = ObjectStorageMapsObjects(storage, _cache(tmp_path))
    for _ in range(2):
        with pytest.raises(MapsObjectMissingError):
            objects.read("maps/none.geojson")
    assert storage.reads == 2


def test_without_cache_every_read_goes_to_storage() -> None:
    storage = _Storage()
    objects = ObjectStorageMapsObjects(storage)
    objects.read("maps/a.geojson")
    objects.read("maps/a.geojson")
    assert storage.reads == 2
