import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.keyvalue_resources import (
    KeyValueResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import PythonAdapter
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


def _kv() -> KeyValueService:
    kv = KeyValueService(PythonAdapter())
    for name, value in fixtures.SEED_ITEMS.items():
        kv.set(name, value)
    return kv


class TestKeyValueResources(ServiceResourcesContract):
    @pytest.fixture
    def resources(self):
        return KeyValueResources(_kv())


class TestKeyValueResourcesOnSQLite(ServiceResourcesContract):
    @pytest.fixture
    def resources(self, tmp_path):
        kv = KeyValueService(PythonAdapter(persistence_path=str(tmp_path / "kv.sqlite")))
        for name, value in fixtures.SEED_ITEMS.items():
            kv.set(name, value)
        return KeyValueResources(kv)


def test_keys_with_slashes_stay_flat():
    kv = _kv()
    kv.set("lock:object:finance/billing/graph.ttl", b"token")
    resources = KeyValueResources(kv)

    names = [e.name for e in asyncio.run(resources.list()).entries]

    assert "lock:object:finance/billing/graph.ttl" in names
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.list("lock:object:finance"))
    with pytest.raises(InvalidResource):
        asyncio.run(resources.list("lock:object:finance/billing/graph.ttl"))


def test_expiring_keys_show_their_ttl_and_keep_it_when_replaced():
    kv = _kv()
    kv.set("session:1", b"old", ttl=300)
    resources = KeyValueResources(kv)

    entry = asyncio.run(resources.stat("session:1"))
    asyncio.run(resources.write("session:1", b"new"))

    assert 0 < int(entry.attributes["expires_in_seconds"]) <= 300
    assert kv.get("session:1") == b"new"
    assert 0 < kv.get_ttl("session:1") <= 300
    assert "expires_in_seconds" not in asyncio.run(resources.stat("alpha")).attributes


def test_binary_values_preview_as_binary_and_download_whole():
    kv = _kv()
    kv.set("blob", b"\x89PNG\x00\x01")
    resources = KeyValueResources(kv)

    detail = asyncio.run(resources.read("blob"))

    assert (detail.content.encoding, detail.content.text, detail.content.size) == (
        "binary",
        None,
        6,
    )
    assert asyncio.run(resources.download("blob", max_bytes=100)) == b"\x89PNG\x00\x01"


def test_an_empty_key_cannot_be_written():
    with pytest.raises(InvalidResource):
        asyncio.run(KeyValueResources(_kv()).write("", b"x"))


def test_rows_describe_their_value_and_expiry():
    kv = _kv()
    kv.set("config:flags", b'{"beta": true, "limits": [1, 2]}')
    kv.set("lock:job", b"\x00\x01holder", ttl=90)
    resources = KeyValueResources(kv)

    rows = {e.id: e for e in asyncio.run(resources.list()).entries}

    flags, lock, alpha = rows["config:flags"], rows["lock:job"], rows["alpha"]
    assert flags.attributes["encoding"] == "json"
    assert flags.attributes["summary"] == '{"beta": true, "limits": [1, 2]}'
    assert flags.size == len(b'{"beta": true, "limits": [1, 2]}')
    assert lock.attributes["encoding"] == "binary"
    assert "summary" not in lock.attributes
    assert 0 < int(lock.attributes["expires_in_seconds"]) <= 90
    assert lock.attributes["expires_at"].endswith("+00:00")
    assert (alpha.attributes["encoding"], alpha.attributes["summary"]) == ("text", "first value")
    assert "expires_at" not in alpha.attributes


def test_long_text_summaries_are_one_clipped_line():
    kv = _kv()
    kv.set("note", ("line one\n   line two " + "x" * 400).encode())

    (note,) = [e for e in asyncio.run(KeyValueResources(kv).list()).entries if e.id == "note"]

    assert note.attributes["summary"].startswith("line one line two x")
    assert len(note.attributes["summary"]) == 120
    assert note.attributes["summary"].endswith("…")


def test_search_keeps_keys_containing_the_text_and_pages():
    kv = _kv()
    for i in range(5):
        kv.set(f"session:{i}", b"s")
    kv.set("lock:SESSION-sweeper", b"l")
    resources = KeyValueResources(kv)

    assert resources.capabilities.search is True
    first = asyncio.run(resources.list(limit=4, query="Session"))
    rest = asyncio.run(resources.list(cursor=first.next_cursor, limit=4, query="Session"))

    found = [e.id for e in first.entries + rest.entries]
    assert found == [
        "lock:SESSION-sweeper",
        "session:0",
        "session:1",
        "session:2",
        "session:3",
        "session:4",
    ]
    assert rest.next_cursor is None
    assert asyncio.run(resources.list(query="nothing-like-this")).entries == ()


def test_search_hands_back_a_cursor_after_scanning_its_budget(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary import (
        keyvalue_resources,
    )

    monkeypatch.setattr(keyvalue_resources, "SEARCH_SCAN", 2)
    monkeypatch.setattr(keyvalue_resources, "MAX_KEYS_PER_PAGE", 2)
    kv = _kv()
    kv.set("zz-match", b"m")
    resources = KeyValueResources(kv)

    page = asyncio.run(resources.list(query="match"))

    assert page.entries == ()
    assert page.next_cursor == "beta"
    later = asyncio.run(resources.list(cursor=page.next_cursor, query="match"))
    assert [e.id for e in later.entries] == ["zz-match"]


def test_a_key_expiring_while_listed_is_skipped():
    kv = _kv()
    resources = KeyValueResources(kv)
    original = kv.get

    def gone(key):
        if key == "beta":
            from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError

            raise KVNotFoundError(key)
        return original(key)

    kv.get = gone

    assert [e.id for e in asyncio.run(resources.list()).entries] == ["alpha", "gamma"]


def test_a_key_can_be_written_with_an_expiry():
    kv = _kv()
    resources = KeyValueResources(kv)

    assert resources.capabilities.expiry
    created = asyncio.run(resources.write("cache:x", b"v", ttl_seconds=60))
    assert 0 < int(created.attributes["expires_in_seconds"]) <= 60
    asyncio.run(resources.write("cache:x", b"w", ttl_seconds=3600))
    assert 60 < kv.get_ttl("cache:x") <= 3600 and kv.get("cache:x") == b"w"
