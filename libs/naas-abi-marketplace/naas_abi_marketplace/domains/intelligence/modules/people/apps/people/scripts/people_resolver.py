"""Resolve people directory data: DuckLake datasets or live SPARQL over graphs.

Backends (``data.backend``):

- ``dataset``: one platform dataset (``make people-datasets``).
- ``workspace_dataset``: in Nexus, the materialized dataset of each people graph
  the workspace may read (``graph_datasets``). The production path.
- ``workspace_graphs``: in Nexus, those graphs merged and exported on the first
  request. Fine for a small graph or development; slow on a large one.
- ``file_graphs``: the configured TTL files.

Nexus (``GraphAccessScope``) decides which graphs a workspace reads; the config
only narrows that set. With a ``workspace_id``, neither workspace backend falls
back to the TTL files: a workspace with no people graph gets a 404 that names
the sync job, never another directory's people.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    graph_datasets,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    triple_store_graph as tg,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.memory_people_store import (
    MemoryPeopleStore,
    PeopleStore,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    DEMO_GRAPH_FILE,
)
from rdflib import Graph

_CACHE_MAX = 12
# Datasets are rows, not graphs: small enough to keep one per workspace.
_DATASET_CACHE_MAX = 128
_sparql_cache: OrderedDict[str, SparqlPeopleSnapshot] = OrderedDict()
_dataset_cache: OrderedDict[str, MemoryPeopleStore] = OrderedDict()
# One entry per graph dataset: workspaces granted the same platform directory
# share its rows instead of each reading them again.
_namespace_cache: OrderedDict[str, dict[str, list[dict[str, Any]]]] = OrderedDict()
_graph_cache: OrderedDict[str, Graph] = OrderedDict()
# A thread lock, not an asyncio one: the dataset refresher fills the same
# caches from its own thread. Held only around dict operations.
_cache_lock = threading.Lock()
_refreshers: set[str] = set()


@dataclass(frozen=True)
class SparqlPeopleSnapshot:
    store: MemoryPeopleStore
    graph: Graph


def _graph_files(config: dict[str, Any]) -> list[Path]:
    graph = config["data"]["graph"]
    configured = graph.get("files") or ([graph["file"]] if graph.get("file") else [])
    paths = [Path(name) for name in configured]
    return paths or [DEMO_GRAPH_FILE]


def _file_cache_key(config: dict[str, Any]) -> str:
    parts = [
        f"{path}:{path.stat().st_mtime_ns}"
        for path in _graph_files(config)
        if path.is_file()
    ]
    return "files:" + "|".join(parts)


@lru_cache(maxsize=8)
def _graph_from_files_key(files: tuple[tuple[str, int], ...]) -> Graph:
    graph = Graph()
    for name, _mtime in files:
        graph.parse(name, format="turtle")
    return graph


def graph_from_config_files(config: dict[str, Any]) -> Graph:
    key = tuple((str(path), path.stat().st_mtime_ns) for path in _graph_files(config))
    return _graph_from_files_key(key)


WORKSPACE_BACKENDS = ("workspace_graphs", "workspace_dataset")


class NoPeopleGraphError(LookupError):
    """The workspace may read no people graph this app is configured for."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(
            f"Workspace {workspace_id} has no people graph. Run: {graph_datasets.SYNC_COMMAND}"
        )


def filter_graph_iris(readable: frozenset[str], config: dict[str, Any]) -> list[str]:
    """The readable graphs this instance lists people from.

    ``data.graph.iri`` (the instance's own directory) counts when Nexus lets the
    workspace read it: the policy grants it, the config never does.
    """
    graph = config["data"]["graph"]
    prefixes = graph.get("include_prefixes") or []
    suffixes = graph.get("include_suffixes") or []
    if not prefixes and not suffixes:
        return sorted(readable)
    return sorted(
        iri
        for iri in readable
        if iri == graph.get("iri")
        or any(str(iri).startswith(prefix) for prefix in prefixes)
        or any(str(iri).rstrip("/").endswith(suffix) for suffix in suffixes)
    )


def _triple_store() -> Any:
    try:
        from intelligence.people_intelligence.apps.people import (
            ABIModule as FmzModule,
        )

        module = FmzModule.get_instance()
        if module is not None and module.engine.services.triple_store_available():
            return module.engine.services.triple_store.load()
    except Exception:  # noqa: BLE001
        pass
    try:
        from naas_abi_marketplace.domains.intelligence.modules.people.apps.people import (
            ABIModule,
        )

        module = ABIModule.get_instance()
        if module is not None and module.engine.services.triple_store_available():
            return module.engine.services.triple_store.load()
    except Exception:  # noqa: BLE001
        pass
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    return EngineConfiguration.load_configuration().services.triple_store.load()


def _dataset_service() -> Any:
    try:
        from intelligence.people_intelligence.apps.people import (
            ABIModule as FmzModule,
        )

        module = FmzModule.get_instance()
        if module is not None and module.engine.services.dataset_available():
            return module.engine.services.dataset
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"people dataset: no engine module, using the app's own: {exc}")
    from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.api.service import (
        dataset_service,
    )

    return dataset_service()


def _cache_get(cache: OrderedDict[str, Any], key: str) -> Any:
    with _cache_lock:
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value


def _cache_put(
    cache: OrderedDict[str, Any], key: str, value: Any, limit: int = _CACHE_MAX
) -> None:
    with _cache_lock:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)


async def _cached(
    cache: OrderedDict[str, Any], key: str, build: Any, limit: int = _CACHE_MAX
) -> Any:
    cached = _cache_get(cache, key)
    if cached is not None:
        return cached
    value = await asyncio.to_thread(build)
    _cache_put(cache, key, value, limit)
    return value


def _build_snapshot_from_graph(
    graph: Graph, config: dict[str, Any]
) -> SparqlPeopleSnapshot:
    store = MemoryPeopleStore.from_graph(graph, config)
    return SparqlPeopleSnapshot(store=store, graph=graph)


def _build_snapshot_sync(
    config: dict[str, Any], *, graph_iris: tuple[str, ...] | None
) -> SparqlPeopleSnapshot:
    if graph_iris:
        merged, _read = tg.merge_named_graphs(_triple_store(), list(graph_iris))
        return _build_snapshot_from_graph(merged, config)
    graph = graph_from_config_files(config)
    return _build_snapshot_from_graph(graph, config)


async def workspace_readable_iris(user_id: str, workspace_id: str) -> frozenset[str]:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
        require_workspace_access,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
        load_workspace_scope,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
        GraphAccessError,
    )
    from naas_abi.apps.nexus.apps.api.app.services.registry import (
        ServiceRegistry,
    )

    try:
        role = await require_workspace_access(user_id, workspace_id)
        store = ServiceRegistry.instance().graph._get_catalog_store()
        async with AsyncSessionLocal() as session:
            scope = await load_workspace_scope(session, store, workspace_id, role)
        return scope.readable
    except GraphAccessError as exc:
        raise PermissionError(str(exc)) from exc


async def resolve_sparql_snapshot(
    config: dict[str, Any],
    *,
    workspace_id: str | None,
    user_id: str | None,
) -> SparqlPeopleSnapshot | None:
    """Merged graph + tables for SPARQL backends, cached per workspace / file set."""
    backend = config["data"].get("backend") or "dataset"
    if backend == "dataset":
        return None

    graph_iris: tuple[str, ...] | None = None
    if backend == "workspace_graphs" and workspace_id and user_id:
        graph_iris = await workspace_people_iris(config, workspace_id, user_id)
        cache_key = f"ws:{workspace_id}:{'|'.join(graph_iris)}"
    else:
        cache_key = _file_cache_key(config)

    return await _cached(
        _sparql_cache,
        cache_key,
        lambda: _build_snapshot_sync(config, graph_iris=graph_iris),
    )


async def workspace_people_iris(
    config: dict[str, Any], workspace_id: str, user_id: str
) -> tuple[str, ...]:
    """The people graphs *user_id* may read in *workspace_id*; never empty."""
    readable = await workspace_readable_iris(user_id, workspace_id)
    iris = filter_graph_iris(readable, config)
    if not iris:
        logger.warning(
            f"No readable people graph for workspace {workspace_id}; "
            f"readable={sorted(readable)}."
        )
        raise NoPeopleGraphError(workspace_id)
    return tuple(iris)


async def resolve_workspace_dataset(
    config: dict[str, Any],
    *,
    workspace_id: str,
    user_id: str,
) -> tuple[MemoryPeopleStore, tuple[str, ...]]:
    """The materialized people of every graph the workspace may read.

    Cached until one of those datasets gets a new snapshot, so a sync shows up
    on the next request without a restart. A request costs one version check
    per graph; the rows are read only when a version moves.
    """
    graph_iris = await workspace_people_iris(config, workspace_id, user_id)
    service = _dataset_service()
    namespaces = [graph_datasets.graph_namespace(config, iri) for iri in graph_iris]
    versions = await asyncio.to_thread(
        lambda: [
            graph_datasets.dataset_version(service, config, namespace)
            for namespace in namespaces
        ]
    )
    written = [
        f"{namespace}@{version}"
        for namespace, version in zip(namespaces, versions)
        if version is not None
    ]
    if not written:
        raise graph_datasets.missing_error(config, namespaces)

    key = "|".join(written)
    store = _cache_get(_dataset_cache, key)
    if store is None:
        store = await asyncio.to_thread(
            lambda: graph_datasets.merge_tables(
                config,
                [
                    _namespace_tables(service, config, *entry.rsplit("@", 1))
                    for entry in written
                ],
            )
        )
        _cache_put(_dataset_cache, key, store, _DATASET_CACHE_MAX)
    return store, graph_iris


def _namespace_tables(
    service: Any, config: dict[str, Any], namespace: str, version: str
) -> dict[str, list[dict[str, Any]]]:
    """The rows of *namespace* at *version*, read once per version."""
    key = f"{namespace}@{version}"
    tables = _cache_get(_namespace_cache, key)
    if tables is None:
        tables = graph_datasets.read_namespace(service, config, namespace) or {}
        _cache_put(_namespace_cache, key, tables, _DATASET_CACHE_MAX)
        with _cache_lock:
            for stale in [k for k in _namespace_cache if k.startswith(f"{namespace}@")]:
                if stale != key:
                    del _namespace_cache[stale]
    return tables


def refresh_workspace_datasets(config: dict[str, Any]) -> int:
    """Read every graph dataset of this instance whose version is not cached yet.

    Returns how many were read. A dataset is a few table scans, each a fraction
    of a second on DuckLake: the first search of a workspace would otherwise pay
    them, after every restart and after every sync.
    """
    service = _dataset_service()
    prefix = f"{config['data']['namespace']}__"
    namespaces = sorted(
        {info.namespace for info in service.list() if info.namespace.startswith(prefix)}
    )
    read = 0
    for namespace in namespaces:
        version = graph_datasets.dataset_version(service, config, namespace)
        if version is None or _cache_get(_namespace_cache, f"{namespace}@{version}"):
            continue
        try:
            _namespace_tables(service, config, namespace, str(version))
        except Exception as exc:  # noqa: BLE001 - one bad dataset must not stop the rest
            logger.warning(f"people datasets: could not read {namespace}: {exc}")
            continue
        read += 1
    return read


def start_dataset_refresher(
    config: dict[str, Any], *, interval_seconds: float = 300.0
) -> bool:
    """Keep this instance's graph datasets cached, from a daemon thread.

    Reads them all at once, then re-reads the ones a sync changed every
    *interval_seconds*. Requests still check versions, so a change shows up on
    the next request either way; this only moves the read off it. For the API
    server's startup, never a job: one thread per instance namespace.
    """
    name = config["data"]["namespace"]
    with _cache_lock:
        if name in _refreshers:
            return False
        _refreshers.add(name)

    def run() -> None:
        while True:
            started = time.monotonic()
            try:
                read = refresh_workspace_datasets(config)
                if read:
                    logger.info(
                        f"people datasets: cached {read} for {name} in "
                        f"{time.monotonic() - started:.1f}s"
                    )
            except Exception as exc:  # noqa: BLE001 - retried on the next round
                logger.warning(f"people datasets: refresh of {name} failed: {exc}")
            time.sleep(interval_seconds)

    threading.Thread(target=run, name=f"people-datasets-{name}", daemon=True).start()
    return True


async def resolve_workspace_graph(graph_iris: tuple[str, ...]) -> Graph:
    """The merged graphs, for the pages that query a person's triples.

    Search never needs this; a profile's graph view and query runner do.
    """
    return await _cached(
        _graph_cache,
        "|".join(graph_iris),
        lambda: tg.merge_named_graphs(_triple_store(), list(graph_iris))[0],
    )


def _uses_workspace_dataset(
    config: dict[str, Any], workspace_id: str | None, user_id: str | None
) -> bool:
    return bool(
        config["data"].get("backend") == "workspace_dataset"
        and workspace_id
        and user_id
    )


async def resolve_people_store(
    config: dict[str, Any],
    *,
    workspace_id: str | None,
    user_id: str | None,
) -> PeopleStore:
    if _uses_workspace_dataset(config, workspace_id, user_id):
        store, _iris = await resolve_workspace_dataset(
            config, workspace_id=str(workspace_id), user_id=str(user_id)
        )
        return store
    snapshot = await resolve_sparql_snapshot(
        config, workspace_id=workspace_id, user_id=user_id
    )
    if snapshot is None:
        from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.api.service import (
            dataset_service,
        )

        return dataset_service()
    return snapshot.store


async def resolve_graph(
    config: dict[str, Any],
    *,
    workspace_id: str | None,
    user_id: str | None,
) -> Graph:
    if _uses_workspace_dataset(config, workspace_id, user_id):
        iris = await workspace_people_iris(config, str(workspace_id), str(user_id))
        return await resolve_workspace_graph(iris)
    snapshot = await resolve_sparql_snapshot(
        config, workspace_id=workspace_id, user_id=user_id
    )
    if snapshot is not None:
        return snapshot.graph
    return graph_from_config_files(config)
