"""Resolve people directory data: DuckLake datasets or live SPARQL over graphs."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

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
_sparql_cache: OrderedDict[str, SparqlPeopleSnapshot] = OrderedDict()
_cache_lock = asyncio.Lock()


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
        f"{path}:{path.stat().st_mtime_ns}" for path in _graph_files(config) if path.is_file()
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


def filter_graph_iris(readable: frozenset[str], config: dict[str, Any]) -> list[str]:
    prefixes = config["data"]["graph"].get("include_prefixes") or []
    if not prefixes:
        return sorted(readable)
    return sorted(
        iri for iri in readable if any(str(iri).startswith(prefix) for prefix in prefixes)
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


def _build_snapshot_from_graph(graph: Graph, config: dict[str, Any]) -> SparqlPeopleSnapshot:
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
    cache_key = backend
    if backend == "workspace_graphs" and workspace_id and user_id:
        readable = await workspace_readable_iris(user_id, workspace_id)
        iris = filter_graph_iris(readable, config)
        if not iris:
            raise LookupError(
                "No readable graphs match this workspace for the people app"
            )
        graph_iris = tuple(iris)
        cache_key = f"ws:{workspace_id}:{'|'.join(graph_iris)}"
    else:
        cache_key = _file_cache_key(config)

    async with _cache_lock:
        cached = _sparql_cache.get(cache_key)
        if cached is not None:
            _sparql_cache.move_to_end(cache_key)
            return cached

    snapshot = await asyncio.to_thread(
        _build_snapshot_sync, config, graph_iris=graph_iris
    )

    async with _cache_lock:
        _sparql_cache[cache_key] = snapshot
        _sparql_cache.move_to_end(cache_key)
        while len(_sparql_cache) > _CACHE_MAX:
            _sparql_cache.popitem(last=False)
    return snapshot


async def resolve_people_store(
    config: dict[str, Any],
    *,
    workspace_id: str | None,
    user_id: str | None,
) -> PeopleStore:
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
    snapshot = await resolve_sparql_snapshot(
        config, workspace_id=workspace_id, user_id=user_id
    )
    if snapshot is not None:
        return snapshot.graph
    return graph_from_config_files(config)
