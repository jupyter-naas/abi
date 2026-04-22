"""Engine configuration for the Cache service.

Supported adapters
------------------
* ``fs``             – file-system backed (default, no external dependency)
* ``redis``          – Redis backed (requires ``redis`` package)
* ``object_storage`` – object-storage backed; wired automatically after the
                       engine starts, so it shares the same object-storage
                       instance as the rest of the engine.

Example YAML configuration
--------------------------
::

    services:
      cache:
        cache_adapter:
          adapter: "redis"
          config:
            redis_url: "{{ secret.REDIS_URL }}"
            prefix: "naas:cache"

    services:
      cache:
        cache_adapter:
          adapter: "object_storage"
          config:
            cache_prefix: "cache"

    services:
      cache:
        cache_adapter:
          adapter: "fs"
          config:
            base_path: "storage/cache"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.cache.CachePort import ICacheAdapter
from naas_abi_core.services.cache.CacheService import CacheService
from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine


# ---------------------------------------------------------------------------
# Per-adapter configuration models
# ---------------------------------------------------------------------------


class CacheAdapterFSConfiguration(BaseModel):
    """File-system cache adapter configuration."""

    model_config = ConfigDict(extra="forbid")

    base_path: str = "storage/cache"


class CacheAdapterRedisConfiguration(BaseModel):
    """Redis cache adapter configuration."""

    model_config = ConfigDict(extra="forbid")

    redis_url: str = "redis://localhost:6379/0"
    prefix: str = "naas:cache"
    socket_timeout: float | None = None


class CacheAdapterObjectStorageConfiguration(BaseModel):
    """Object-storage cache adapter configuration.

    The ``ObjectStorageService`` is injected automatically when the engine
    wires its services, so no connection parameters are needed here.
    """

    model_config = ConfigDict(extra="forbid")

    cache_prefix: str = "cache"


# ---------------------------------------------------------------------------
# Deferred object-storage backed CacheService
# ---------------------------------------------------------------------------


class _NoOpCacheAdapter(ICacheAdapter):
    """Placeholder adapter that fails loudly if called before wiring."""

    def _fail(self) -> None:  # pragma: no cover
        raise RuntimeError(
            "ObjectStorageBackedCacheService has not been wired yet. "
            "Ensure engine.wire_services() is called before using this service."
        )

    def get(self, key):  # type: ignore[override]
        self._fail()

    def set(self, key, value):  # type: ignore[override]
        self._fail()

    def set_if_absent(self, key, value):  # type: ignore[override]
        self._fail()

    def delete(self, key):  # type: ignore[override]
        self._fail()

    def exists(self, key):  # type: ignore[override]
        self._fail()


class ObjectStorageBackedCacheService(CacheService):
    """CacheService that lazily wires its object-storage adapter.

    When the engine calls ``wire_services()`` this subclass replaces the
    placeholder adapter with a real ``CacheObjectStorageAdapter`` using the
    already-loaded ``ObjectStorageService``.
    """

    def __init__(self, cache_prefix: str = "cache") -> None:
        super().__init__(adapter=_NoOpCacheAdapter())
        self._cache_prefix = cache_prefix

    def set_services(self, services: "IEngine.Services") -> None:
        super().set_services(services)
        from naas_abi_core.services.cache.adapters.secondary.CacheObjectStorageAdapter import (
            CacheObjectStorageAdapter,
        )

        self.adapter = CacheObjectStorageAdapter(
            object_storage=services.object_storage,
            prefix=self._cache_prefix,
        )


# ---------------------------------------------------------------------------
# Unified adapter configuration
# ---------------------------------------------------------------------------


class CacheAdapterConfiguration(GenericLoader):
    adapter: Literal["fs", "redis", "object_storage", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "CacheAdapterConfiguration":
        if self.adapter == "custom":
            return self

        assert self.config is not None, (
            "config is required when adapter is not 'custom'"
        )

        if self.adapter == "fs":
            pydantic_model_validator(
                CacheAdapterFSConfiguration,
                self.config,
                "Invalid configuration for services.cache.cache_adapter 'fs' adapter",
            )
        elif self.adapter == "redis":
            pydantic_model_validator(
                CacheAdapterRedisConfiguration,
                self.config,
                "Invalid configuration for services.cache.cache_adapter 'redis' adapter",
            )
        elif self.adapter == "object_storage":
            pydantic_model_validator(
                CacheAdapterObjectStorageConfiguration,
                self.config,
                "Invalid configuration for services.cache.cache_adapter 'object_storage' adapter",
            )

        return self

    def load(self) -> CacheService:  # type: ignore[override]
        """Return a fully constructed (or deferred) ``CacheService``."""

        if self.adapter == "custom":
            # GenericLoader.load() instantiates an arbitrary class from config
            return super().load()  # type: ignore[return-value]

        assert self.config is not None

        if self.adapter == "fs":
            cfg = CacheAdapterFSConfiguration(**self.config)
            from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
                CacheFSAdapter,
            )

            return CacheService(adapter=CacheFSAdapter(cfg.base_path))

        if self.adapter == "redis":
            cfg = CacheAdapterRedisConfiguration(**self.config)
            from naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter import (
                CacheRedisAdapter,
            )

            return CacheService(
                adapter=CacheRedisAdapter(
                    redis_url=cfg.redis_url,
                    prefix=cfg.prefix,
                    socket_timeout=cfg.socket_timeout,
                )
            )

        if self.adapter == "object_storage":
            cfg = CacheAdapterObjectStorageConfiguration(**self.config)
            return ObjectStorageBackedCacheService(cache_prefix=cfg.cache_prefix)

        raise ValueError(f"Unknown cache adapter: {self.adapter!r}")


# ---------------------------------------------------------------------------
# Top-level service configuration
# ---------------------------------------------------------------------------


class CacheServiceConfiguration(BaseModel):
    cache_adapter: CacheAdapterConfiguration

    def load(self) -> CacheService:
        return self.cache_adapter.load()
