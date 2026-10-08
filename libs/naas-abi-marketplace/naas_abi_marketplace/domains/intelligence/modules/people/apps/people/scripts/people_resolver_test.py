"""Tests for in-memory people data built from graph export rows."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    people_resolver as pr,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.memory_people_store import (
    MemoryPeopleStore,
)

CONFIG = load_config()


def _store(rows: list[dict]) -> MemoryPeopleStore:
    return MemoryPeopleStore({"people": rows}, CONFIG)


def test_fetch_people_by_slug() -> None:
    store = _store([{"slug": "ada", "full_name": "Ada", "search_text": "ada engineer"}])
    found = store.fetch_people(
        namespace="people",
        table="people",
        where="slug = 'ada'",
        limit=1,
    )
    assert found[0]["slug"] == "ada"


def test_search_text_like_via_fetch_people() -> None:
    store = _store(
        [
            {"slug": "a", "full_name": "A", "search_text": "audit partner france"},
            {"slug": "b", "full_name": "B", "search_text": "tax advisor"},
        ]
    )
    where = "(search_text LIKE 'audit%' OR search_text LIKE '% audit%')"
    hits = ds.fetch_people(
        store, namespace="people", table="people", where=where, limit=10
    )
    assert [row["slug"] for row in hits] == ["a"]


# --- Which graphs and which backend serve a workspace ---------------------

AXA_PEOPLE = "http://ontology.naas.ai/graph/ws-1fe2cd925ef1/people"
AXA_MARKET = "http://ontology.naas.ai/graph/ws-1fe2cd925ef1/market"
AXA_KG = "http://ontology.naas.ai/graph/axa"
FMZ_DIRECTORY = "http://ontology.naas.ai/graph/people/forvismazars"
PLATFORM_BOARDS = "http://ontology.naas.ai/graph/people/market_intelligence"


def _workspace_config(backend: str = "workspace_dataset") -> dict[str, Any]:
    return {
        **CONFIG,
        "data": {
            **CONFIG["data"],
            "backend": backend,
            "namespace": "people_fmz",
            "graph": {
                **CONFIG["data"]["graph"],
                "iri": FMZ_DIRECTORY,
                "include_prefixes": [],
                "include_suffixes": ["/people"],
            },
        },
    }


def test_client_workspace_reads_only_its_own_people_graph() -> None:
    readable = frozenset({AXA_PEOPLE, AXA_MARKET, AXA_KG})
    assert pr.filter_graph_iris(readable, _workspace_config()) == [AXA_PEOPLE]


def test_platform_people_graphs_need_a_nexus_grant() -> None:
    config = _workspace_config()
    assert pr.filter_graph_iris(frozenset({AXA_PEOPLE}), config) == [AXA_PEOPLE]
    granted = frozenset({AXA_PEOPLE, FMZ_DIRECTORY, PLATFORM_BOARDS})
    # The instance's own directory counts once Nexus grants it; another
    # platform people graph does not match the suffix and stays out.
    assert pr.filter_graph_iris(granted, config) == sorted([AXA_PEOPLE, FMZ_DIRECTORY])


@pytest.mark.parametrize("backend", ["workspace_graphs", "workspace_dataset"])
def test_no_people_graph_is_a_lookup_error_not_a_ttl_fallback(
    monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    async def readable(_user: str, _ws: str) -> frozenset[str]:
        return frozenset({AXA_MARKET, AXA_KG})

    monkeypatch.setattr(pr, "workspace_readable_iris", readable)

    def no_files(_config: dict[str, Any]) -> Any:
        raise AssertionError("TTL files must not be read for a workspace")

    monkeypatch.setattr(pr, "graph_from_config_files", no_files)
    with pytest.raises(pr.NoPeopleGraphError, match="people_intelligence_sync"):
        asyncio.run(
            pr.resolve_people_store(
                _workspace_config(backend), workspace_id="ws-1fe2cd925ef1", user_id="u"
            )
        )


def test_workspace_dataset_reads_the_materialized_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def readable(_user: str, _ws: str) -> frozenset[str]:
        return frozenset({AXA_PEOPLE, AXA_KG})

    loaded: list[list[str]] = []

    def load_store(_service: Any, config: dict[str, Any], namespaces: list[str]) -> Any:
        loaded.append(namespaces)
        return MemoryPeopleStore({"people": []}, config)

    def merge(*_args: Any) -> Any:
        raise AssertionError("search must not merge graphs in workspace_dataset")

    monkeypatch.setattr(pr, "workspace_readable_iris", readable)
    monkeypatch.setattr(pr, "_dataset_service", lambda: object())
    monkeypatch.setattr(pr.graph_datasets, "dataset_version", lambda *_a: 7)
    monkeypatch.setattr(pr.graph_datasets, "load_store", load_store)
    monkeypatch.setattr(pr.tg, "merge_named_graphs", merge)
    pr._dataset_cache.clear()

    config = _workspace_config()
    for _ in range(2):
        asyncio.run(
            pr.resolve_people_store(config, workspace_id="ws-1fe2cd925ef1", user_id="u")
        )

    # Built once, then served from the cache while the snapshot is unchanged.
    assert loaded == [["people_fmz__ws_1fe2cd925ef1_people"]]


def test_a_new_snapshot_invalidates_the_cached_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def readable(_user: str, _ws: str) -> frozenset[str]:
        return frozenset({AXA_PEOPLE})

    version = {"n": 1}
    builds: list[int] = []

    def load_store(_service: Any, config: dict[str, Any], _ns: list[str]) -> Any:
        builds.append(version["n"])
        return MemoryPeopleStore({"people": []}, config)

    monkeypatch.setattr(pr, "workspace_readable_iris", readable)
    monkeypatch.setattr(pr, "_dataset_service", lambda: object())
    monkeypatch.setattr(pr.graph_datasets, "dataset_version", lambda *_a: version["n"])
    monkeypatch.setattr(pr.graph_datasets, "load_store", load_store)
    pr._dataset_cache.clear()

    config = _workspace_config()
    for n in (1, 2):
        version["n"] = n
        asyncio.run(
            pr.resolve_people_store(config, workspace_id="ws-1fe2cd925ef1", user_id="u")
        )

    assert builds == [1, 2]
