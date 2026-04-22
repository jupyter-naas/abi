"""Engine configuration for the Cache service.

Supported adapters per tier
---------------------------
* ``fs``             – file-system backed (no external dependency)
* ``redis``          – Redis backed (requires ``redis`` package)
* ``object_storage`` – uses the engine's ObjectStorageService, wired
                       automatically once the engine starts

Tier conventions
----------------
* ``hot``  – fast, possibly volatile (Redis, in-memory)
* ``cold`` – durable, slower (object-storage, filesystem) [**default**]

Example: single cold tier (default, equivalent to the previous single-adapter API)
::

    services:
      cache:
        adapters:
          - adapter: fs
            tier: cold
            config:
              base_path: "storage/cache"

Example: Redis hot + object-storage cold
::

    services:
      cache:
        adapters:
          - adapter: redis
            tier: hot
            config:
              redis_url: "{{ secret.REDIS_URL }}"
              prefix: "naas:cache"
          - adapter: object_storage
            tier: cold
            config:
              cache_prefix: "cache"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.cache.CachePort import CachedData, ICacheAdapter
from naas_abi_core.services.cache.CacheService import CacheService
from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine

# Tier name constants — defined early so they can be used as defaults below
TIER_HOT = "hot"
TIER_COLD = "cold"


# ---------------------------------------------------------------------------
# Per-adapter configuration models
# ---------------------------------------------------------------------------


class CacheAdapterFSConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_path: str = "storage/cache"


class CacheAdapterRedisConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    redis_url: str = "redis://localhost:6379/0"
    prefix: str = "naas:cache"
    socket_timeout: float | None = None


class CacheAdapterObjectStorageConfiguration(BaseModel):
    """Object-storage adapter — ObjectStorageService injected at engine wiring time."""
    model_config = ConfigDict(extra="forbid")
    cache_prefix: str = "cache"


# ---------------------------------------------------------------------------
# Deferred object-storage adapter (wired via engine's wire_services())
# ---------------------------------------------------------------------------


class _NoOpCacheAdapter(ICacheAdapter):
    """Placeholder that raises loudly if called before wiring."""

    def _fail(self) -> Any:  # pragma: no cover
        raise RuntimeError(
            "ObjectStorageBackedAdapter has not been wired yet. "
            "Ensure engine.wire_services() is called before using the cache."
        )

    def get(self, key: str) -> CachedData: return self._fail()  # type: ignore[return-value]
    def set(self, key: str, value: CachedData) -> None: self._fail()
    def set_if_absent(self, key: str, value: CachedData) -> bool: return self._fail()  # type: ignore[return-value]
    def delete(self, key: str) -> None: self._fail()
    def exists(self, key: str) -> bool: return self._fail()  # type: ignore[return-value]


class ObjectStorageBackedAdapter(ICacheAdapter):
    """ICacheAdapter that lazily initialises CacheObjectStorageAdapter.

    ``wire_services(services)`` is called by ``CacheService.set_services()``
    during engine startup, after ``ObjectStorageService`` is available.
    """

    def __init__(self, cache_prefix: str = "cache") -> None:
        self._cache_prefix = cache_prefix
        self._inner: ICacheAdapter = _NoOpCacheAdapter()

    def wire_services(self, services: "IEngine.Services") -> None:
        from naas_abi_core.services.cache.adapters.secondary.CacheObjectStorageAdapter import (
            CacheObjectStorageAdapter,
        )
        self._inner = CacheObjectStorageAdapter(
            object_storage=services.object_storage,
            prefix=self._cache_prefix,
        )

    def get(self, key: str) -> CachedData:
        return self._inner.get(key)

    def set(self, key: str, value: CachedData) -> None:
        self._inner.set(key, value)

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        return self._inner.set_if_absent(key, value)

    def delete(self, key: str) -> None:
        self._inner.delete(key)

    def exists(self, key: str) -> bool:
        return self._inner.exists(key)


# ---------------------------------------------------------------------------
# Per-entry adapter configuration (one entry = one tier)
# ---------------------------------------------------------------------------


class CacheAdapterEntry(GenericLoader):
    """One adapter entry in the cache stack."""

    adapter: Literal["fs", "redis", "object_storage", "custom"]
    tier: str = TIER_COLD  # "hot" | "cold" | any custom name
    config: dict | None = None

    @model_validator(mode="after")
    def _validate(self) -> "CacheAdapterEntry":
        if self.adapter == "custom":
            return self
        assert self.config is not None, (
            f"config is required for adapter={self.adapter!r}"
        )
        validators = {
            "fs": (CacheAdapterFSConfiguration, "fs"),
            "redis": (CacheAdapterRedisConfiguration, "redis"),
            "object_storage": (CacheAdapterObjectStorageConfiguration, "object_storage"),
        }
        if self.adapter in validators:
            model, name = validators[self.adapter]
            pydantic_model_validator(
                model,
                self.config,
                f"Invalid config for services.cache adapter {name!r}",
            )
        return self

    def load_adapter(self) -> ICacheAdapter:
        """Instantiate and return the raw ``ICacheAdapter``."""
        if self.adapter == "custom":
            return super().load()  # type: ignore[return-value]

        assert self.config is not None

        if self.adapter == "fs":
            cfg = CacheAdapterFSConfiguration(**self.config)
            from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
                CacheFSAdapter,
            )
            return CacheFSAdapter(cfg.base_path)

        if self.adapter == "redis":
            cfg = CacheAdapterRedisConfiguration(**self.config)
            from naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter import (
                CacheRedisAdapter,
            )
            return CacheRedisAdapter(
                redis_url=cfg.redis_url,
                prefix=cfg.prefix,
                socket_timeout=cfg.socket_timeout,
            )

        if self.adapter == "object_storage":
            cfg = CacheAdapterObjectStorageConfiguration(**self.config)
            return ObjectStorageBackedAdapter(cache_prefix=cfg.cache_prefix)

        raise ValueError(f"Unknown cache adapter: {self.adapter!r}")


# ---------------------------------------------------------------------------
# Top-level service configuration
# ---------------------------------------------------------------------------


class CacheServiceConfiguration(BaseModel):
    adapters: list[CacheAdapterEntry] = [
        CacheAdapterEntry(
            adapter="fs",
            tier=TIER_COLD,
            config=CacheAdapterFSConfiguration(base_path="storage/cache").model_dump(),
        )
    ]

    def load(self) -> CacheService:
        return CacheService(
            adapters=[
                (entry.tier, entry.load_adapter()) for entry in self.adapters
            ]
        )
