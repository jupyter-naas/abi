"""Multi-tier cache service.

Tier semantics
--------------
hot  – fast, possibly volatile   (Redis, in-memory)
cold – durable, slower           (object-storage, filesystem)

Read semantics (top-level ``CacheService``)
  ``cache.get(key)``    → hot → cold, **no automatic promotion**
  ``cache.exists(key)`` → any tier, hot first

Write semantics (top-level ``CacheService``)
  ``cache.set_*(key)``  → **cold only**  (explicit = explicit)
  ``cache.delete(key)`` → all tiers

Explicit tier access
  ``cache.hot.set_json(key, value)``            # write to hot only
  ``cache.cold.set_json_if_absent(key, value)`` # write to cold only
  ``cache.hot.get(key)``                        # read from hot only

The ``__call__`` decorator on the top-level service targets cold by default;
to target hot use ``@cache.hot(key_builder, cache_type=…)``.
"""

from __future__ import annotations

import base64
import datetime
import inspect
import json
import pickle
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Callable

from naas_abi_core import logger
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheExpiredError,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
    ICacheService,
)
from naas_abi_core.services.cache.ontologies.modules.CacheEventOntology import (
    CacheDeleted,
    CacheError,
    CacheSet,
)
from naas_abi_core.services.ServiceBase import ServiceBase

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine

TIER_HOT = "hot"
TIER_COLD = "cold"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class ForceRefresh(Exception):
    pass


# ---------------------------------------------------------------------------
# Single-tier view — wraps one ICacheAdapter with all cache operations
# ---------------------------------------------------------------------------


class SingleTierCacheService:
    """All cache operations scoped to a single adapter/tier.

    Instances are never created directly by callers — they are exposed through
    :attr:`CacheService.hot` and :attr:`CacheService.cold`.
    """

    def __init__(
        self,
        adapter: ICacheAdapter,
        tier_name: str | None = None,
        event_publisher: Callable[[Any], None] | None = None,
    ) -> None:
        self.adapter = adapter
        self._tier_name = tier_name
        self._event_publisher = event_publisher

        self._deserializers = {
            DataType.TEXT: self._get_text,
            DataType.JSON: self._get_json,
            DataType.BINARY: self._get_binary,
            DataType.PICKLE: self._get_pickle,
        }

    # ------------------------------------------------------------------
    # Event emission helpers
    # ------------------------------------------------------------------

    def _emit(self, event: Any) -> None:
        if self._event_publisher is None:
            return
        try:
            self._event_publisher(event)
        except Exception as exc:
            logger.warning(
                "Cache tier %r: event publication failed: %s", self._tier_name, exc
            )

    def _run_mutation(self, op_name: str, key: str, fn: Callable[[], Any]) -> Any:
        """Run an adapter mutation; emit CacheError on unexpected failure.

        CacheNotFoundError propagates without an event — "delete a missing key"
        is a no-op, not an error worth logging.
        """
        try:
            return fn()
        except CacheNotFoundError:
            raise
        except Exception as exc:
            self._emit(
                CacheError(
                    key=key,
                    tier=self._tier_name,
                    operation=op_name,
                    message=str(exc),
                )
            )
            raise

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def __call__(
        self,
        key_builder: Callable,
        cache_type: DataType,
        ttl: datetime.timedelta | None = None,
        auto_cache: bool = True,
    ):
        """Decorator to cache function results in *this* tier.

        Usage::

            @cache.cold(lambda x: f"vectors:{x}", cache_type=DataType.JSON)
            def embed(x): ...

            @cache.hot(lambda x: f"meta:{x}", cache_type=DataType.JSON)
            def fast_lookup(x): ...
        """
        logger.debug(
            "Cache decorator: key_builder=%s auto_cache=%s cache_type=%s ttl=%s",
            key_builder,
            auto_cache,
            cache_type,
            ttl,
        )

        def decorator(func):
            def wrapper(*args, **kwargs):
                mapped_args: OrderedDict = OrderedDict()
                func_args = inspect.signature(func).parameters
                func_args_list = list(func_args.keys())

                for i, arg in enumerate(args):
                    mapped_args[func_args_list[i]] = arg
                for name, val in kwargs.items():
                    if name in func_args_list:
                        mapped_args[name] = val
                for name, param in func_args.items():
                    if param.default is not param.empty and name not in mapped_args:
                        mapped_args[name] = param.default

                key_builder_params = inspect.signature(key_builder).parameters
                filtered = OrderedDict(
                    (k, v) for k, v in mapped_args.items() if k in key_builder_params
                )
                cache_key = key_builder(**filtered)

                try:
                    if "force_cache_refresh" in kwargs:
                        del kwargs["force_cache_refresh"]
                        raise ForceRefresh()
                    cached_data = self._get_cached_data(cache_key, ttl)
                    if cached_data.data_type == cache_type:
                        return self._deserializers[cache_type](cached_data)
                    raise CacheNotFoundError("Data type mismatch")
                except (CacheNotFoundError, CacheExpiredError, ForceRefresh):
                    result = func(*args, **kwargs)
                    if auto_cache:
                        if cache_type == DataType.TEXT:
                            self.set_text(cache_key, result)
                        elif cache_type == DataType.JSON:
                            self.set_json(cache_key, result)
                        elif cache_type == DataType.BINARY:
                            self.set_binary(cache_key, result)
                        elif cache_type == DataType.PICKLE:
                            self.set_pickle(cache_key, result)
                        else:
                            raise ValueError(
                                f"cache_type must be specified. Got: {cache_type}"
                            )
                    return result

            return wrapper

        return decorator

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_cached_data(
        self, key: str, ttl: datetime.timedelta | None = None
    ) -> CachedData:
        try:
            cached_data = self.adapter.get(key)
        except Exception:
            raise CacheNotFoundError(f"Cache not found: {key}")

        if (
            ttl
            and datetime.datetime.fromisoformat(cached_data.created_at) + ttl
            < datetime.datetime.now()
        ):
            raise CacheExpiredError(
                f"Cache expired: {key}. TTL={ttl}. created_at={cached_data.created_at}"
            )
        return cached_data

    @staticmethod
    def _get_text(data: CachedData) -> str:
        return data.data

    @staticmethod
    def _get_json(data: CachedData) -> dict:
        return json.loads(data.data)

    @staticmethod
    def _get_binary(data: CachedData) -> bytes:
        return base64.b64decode(data.data)

    @staticmethod
    def _get_pickle(data: CachedData) -> Any:
        return pickle.loads(base64.b64decode(data.data))  # nosec B301

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, ttl: datetime.timedelta | None = None) -> Any:
        cached_data = self._get_cached_data(key, ttl)
        return self._deserializers[cached_data.data_type](cached_data)

    def exists(self, key: str) -> bool:
        return self.adapter.exists(key)

    def delete(self, key: str) -> None:
        self._run_mutation("delete", key, lambda: self.adapter.delete(key))
        self._emit(CacheDeleted(key=key, tier=self._tier_name))

    def _emit_cache_set(self, key: str, cached: CachedData) -> None:
        self._emit(
            CacheSet(
                key=key,
                tier=self._tier_name,
                data_type=cached.data_type.value,
                size_bytes=len(cached.data)
                if isinstance(cached.data, (str, bytes))
                else None,
            )
        )

    def set_text(self, key: str, value: str) -> None:
        assert isinstance(value, str), f"Expected str, got {type(value)}"
        cached = CachedData(key=key, data=value, data_type=DataType.TEXT)
        self._run_mutation("set", key, lambda: self.adapter.set(key, cached))
        self._emit_cache_set(key, cached)

    def set_json(self, key: str, value: Any) -> None:
        cached = CachedData(key=key, data=json.dumps(value), data_type=DataType.JSON)
        self._run_mutation("set", key, lambda: self.adapter.set(key, cached))
        self._emit_cache_set(key, cached)

    def set_json_if_absent(self, key: str, value: Any) -> bool:
        cached = CachedData(key=key, data=json.dumps(value), data_type=DataType.JSON)
        wrote = self._set_if_absent(key, cached)
        if wrote:
            self._emit_cache_set(key, cached)
        return wrote

    def set_binary(self, key: str, value: bytes) -> None:
        assert isinstance(value, bytes), f"Expected bytes, got {type(value)}"
        cached = CachedData(
            key=key,
            data=base64.b64encode(value).decode(),
            data_type=DataType.BINARY,
        )
        self._run_mutation("set", key, lambda: self.adapter.set(key, cached))
        self._emit_cache_set(key, cached)

    def set_binary_if_absent(self, key: str, value: bytes) -> bool:
        assert isinstance(value, bytes), f"Expected bytes, got {type(value)}"
        cached = CachedData(
            key=key,
            data=base64.b64encode(value).decode(),
            data_type=DataType.BINARY,
        )
        wrote = self._set_if_absent(key, cached)
        if wrote:
            self._emit_cache_set(key, cached)
        return wrote

    def set_pickle(self, key: str, value: Any) -> None:
        cached = CachedData(
            key=key,
            data=base64.b64encode(pickle.dumps(value)).decode(),
            data_type=DataType.PICKLE,
        )
        self._run_mutation("set", key, lambda: self.adapter.set(key, cached))
        self._emit_cache_set(key, cached)

    def _set_if_absent(self, key: str, cached: CachedData) -> bool:
        def _do() -> bool:
            try:
                return self.adapter.set_if_absent(key, cached)
            except NotImplementedError:
                if self.exists(key):
                    return False
                self.adapter.set(key, cached)
                return True

        return self._run_mutation("set", key, _do)


# ---------------------------------------------------------------------------
# Multi-tier orchestrator — the engine-registered service
# ---------------------------------------------------------------------------


class CacheService(ServiceBase, ICacheService):
    """Multi-tier cache service.

    Args:
        adapters: Ordered list of ``(tier_name, ICacheAdapter)`` pairs.
                  Convention: ``"hot"`` adapters come before ``"cold"`` ones.
                  When a single adapter is supplied without a tier name it is
                  treated as ``"cold"`` (durable default).

    Examples::

        # Single cold tier (most common, backward-compatible)
        CacheService(adapters=[("cold", fs_adapter)])

        # Two tiers — hot (Redis) + cold (object storage)
        CacheService(adapters=[("hot", redis_adapter), ("cold", os_adapter)])
    """

    def __init__(self, adapters: list[tuple[str, ICacheAdapter]]) -> None:
        super().__init__()
        if not adapters:
            raise ValueError("CacheService requires at least one adapter")
        self._adapters: list[tuple[str, ICacheAdapter]] = adapters
        self._tiers: dict[str, SingleTierCacheService] = {
            tier: SingleTierCacheService(
                adapter,
                tier_name=tier,
                event_publisher=self.__publish_event,
            )
            for tier, adapter in adapters
        }

    def __publish_event(self, event: Any) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
            # Cache mutations are the source of truth; event logging must not break them.
            logger.warning(f"CacheService: failed to publish event: {exc}")

    # ------------------------------------------------------------------
    # Tier accessors
    # ------------------------------------------------------------------

    @property
    def hot(self) -> SingleTierCacheService:
        """Return the hot-tier view.  Raises if no hot tier is configured."""
        if TIER_HOT not in self._tiers:
            raise ValueError(
                "No 'hot' tier configured. "
                "Add an adapter with tier='hot' to the cache configuration."
            )
        return self._tiers[TIER_HOT]

    @property
    def cold(self) -> SingleTierCacheService:
        """Return the cold-tier view.

        Falls back to the *last* configured adapter when no tier is
        explicitly named ``"cold"``, which preserves single-adapter
        backward compatibility.
        """
        if TIER_COLD in self._tiers:
            return self._tiers[TIER_COLD]
        # Fallback: last adapter is the coldest/most durable
        tier_name, adapter = self._adapters[-1]
        return SingleTierCacheService(
            adapter,
            tier_name=tier_name,
            event_publisher=self.__publish_event,
        )

    def hot_available(self) -> bool:
        """Return True if a hot tier is configured."""
        return TIER_HOT in self._tiers

    # ------------------------------------------------------------------
    # Decorator — delegates to cold tier by default
    # ------------------------------------------------------------------

    def __call__(
        self,
        key_builder: Callable,
        cache_type: DataType,
        ttl: datetime.timedelta | None = None,
        auto_cache: bool = True,
    ):
        """Decorator that caches in the *cold* tier.

        Use ``@cache.hot(…)`` or ``@cache.cold(…)`` to target a specific tier.
        """
        return self.cold(
            key_builder=key_builder,
            cache_type=cache_type,
            ttl=ttl,
            auto_cache=auto_cache,
        )

    # ------------------------------------------------------------------
    # Read — hot → cold read-through, no automatic promotion
    # ------------------------------------------------------------------

    def get(self, key: str, ttl: datetime.timedelta | None = None) -> Any:
        """Read-through across all tiers (hot first).

        No automatic promotion: a cold-tier hit does **not** write to hot.
        If you want to promote, call ``cache.hot.set_*(…)`` explicitly after
        a successful cold read.

        Non-``CacheNotFoundError`` / ``CacheExpiredError`` exceptions from
        intermediate tiers (e.g. Redis connection failures) are logged as
        warnings and treated as misses so the system degrades gracefully.

        Raises :class:`CacheNotFoundError` if the key is absent from every tier.
        """
        for tier_name, adapter in self._adapters:
            try:
                return SingleTierCacheService(adapter).get(key, ttl)
            except (CacheNotFoundError, CacheExpiredError):
                continue
            except Exception as exc:
                logger.warning(
                    "Cache tier %r unavailable during get(%r), falling through: %s",
                    tier_name, key, exc,
                )
                continue
        raise CacheNotFoundError(f"Cache not found in any tier: {key!r}")

    def exists(self, key: str) -> bool:
        """Return True if the key exists in *any* tier (hot checked first).

        Unavailable tiers (e.g. Redis connection failure) are treated as
        misses and logged as warnings.
        """
        for tier_name, adapter in self._adapters:
            try:
                if adapter.exists(key):
                    return True
            except Exception as exc:
                logger.warning(
                    "Cache tier %r unavailable during exists(%r), treating as miss: %s",
                    tier_name, key, exc,
                )
        return False

    # ------------------------------------------------------------------
    # Write — cold only by default
    # ------------------------------------------------------------------

    def delete(self, key: str) -> None:
        """Delete from *all* tiers to keep them consistent."""
        for _, svc in self._tiers.items():
            try:
                svc.delete(key)
            except (CacheNotFoundError, Exception):
                pass  # missing in one tier is fine

    def set_text(self, key: str, value: str) -> None:
        self.cold.set_text(key, value)

    def set_json(self, key: str, value: Any) -> None:
        self.cold.set_json(key, value)

    def set_json_if_absent(self, key: str, value: Any) -> bool:
        return self.cold.set_json_if_absent(key, value)

    def set_binary(self, key: str, value: bytes) -> None:
        self.cold.set_binary(key, value)

    def set_binary_if_absent(self, key: str, value: bytes) -> bool:
        return self.cold.set_binary_if_absent(key, value)

    def set_pickle(self, key: str, value: Any) -> None:
        self.cold.set_pickle(key, value)

    # ------------------------------------------------------------------
    # Engine wiring — forward to any adapter that needs it
    # ------------------------------------------------------------------

    def set_services(self, services: "IEngine.Services") -> None:
        super().set_services(services)
        for _, adapter in self._adapters:
            if hasattr(adapter, "wire_services"):
                adapter.wire_services(services)
