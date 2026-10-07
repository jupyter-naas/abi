"""Tests for in-memory people data built from graph export rows."""

from __future__ import annotations

from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
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
