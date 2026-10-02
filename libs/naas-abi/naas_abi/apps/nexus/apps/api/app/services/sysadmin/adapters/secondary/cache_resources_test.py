import asyncio
import base64
import pickle

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.cache_resources import (
    CacheResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.adapters.secondary.CacheKeyValueAdapter import (
    CacheKeyValueAdapter,
)
from naas_abi_core.services.cache.CacheService import TIER_COLD, TIER_HOT, CacheService
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import PythonAdapter
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


def _cache(tmp_path) -> CacheService:
    """Two real tiers: a filesystem hot tier and a key-value cold tier."""
    cache = CacheService(
        adapters=[
            (TIER_HOT, CacheFSAdapter(str(tmp_path / "hot"))),
            (TIER_COLD, CacheKeyValueAdapter(KeyValueService(PythonAdapter()))),
        ]
    )
    for name, value in fixtures.SEED_ITEMS.items():
        cache.set_text(name, value.decode())
    return cache


class TestCacheResources(ServiceResourcesContract):
    @pytest.fixture
    def resources(self, tmp_path):
        return CacheResources(_cache(tmp_path))


def test_entries_show_their_type_tier_and_creation_time(tmp_path):
    cache = _cache(tmp_path)
    cache.hot.set_json("hot:config", {"a": 1})
    resources = CacheResources(cache)

    hot = asyncio.run(resources.stat("hot:config"))
    cold = asyncio.run(resources.stat("alpha"))

    assert (hot.attributes["data_type"], hot.attributes["tier"]) == ("json", TIER_HOT)
    assert (cold.attributes["data_type"], cold.attributes["tier"]) == ("text", TIER_COLD)
    assert hot.modified and hot.modified == hot.attributes["created_at"]
    assert asyncio.run(resources.read("hot:config")).content.text == '{"a": 1}'
    assert "hot:config" in {e.id for e in asyncio.run(resources.list()).entries}


def test_replacing_updates_every_tier_holding_the_key(tmp_path):
    cache = _cache(tmp_path)
    cache.hot.set_text("only-hot", "old")
    cache.hot.set_text("both", "old")
    cache.cold.set_text("both", "old")
    resources = CacheResources(cache)

    asyncio.run(resources.write("only-hot", b"new"))
    asyncio.run(resources.write("both", b"new"))

    assert cache.hot.get("only-hot") == "new"
    assert not cache.cold.exists("only-hot")
    assert (cache.hot.get("both"), cache.cold.get("both")) == ("new", "new")


def test_delete_removes_the_key_from_every_tier(tmp_path):
    cache = _cache(tmp_path)
    cache.hot.set_text("alpha", "hot copy")
    resources = CacheResources(cache)

    asyncio.run(resources.delete("alpha"))

    assert not cache.exists("alpha")


class _Explodes:
    def __reduce__(self):
        return (_never_called, ())


def _never_called():
    raise AssertionError("the System app must never unpickle a cache entry")


def test_pickle_and_binary_entries_are_never_decoded_for_display(tmp_path):
    cache = _cache(tmp_path)
    cache.set_pickle("pickled", _Explodes())
    cache.set_binary("bytes", b"\x00\x01\x02")
    resources = CacheResources(cache)

    pickled = asyncio.run(resources.read("pickled"))
    raw = asyncio.run(resources.read("bytes"))
    downloaded = asyncio.run(resources.download("pickled", max_bytes=1 << 20))

    assert (pickled.content.encoding, pickled.content.text) == ("binary", None)
    assert pickled.entry.attributes["data_type"] == "pickle"
    assert (raw.content.encoding, raw.content.size) == ("binary", 3)
    assert asyncio.run(resources.download("bytes", max_bytes=10)) == b"\x00\x01\x02"
    # The download is the pickle's bytes, still unloaded.
    assert downloaded == base64.b64decode(cache.get_entry("pickled").cached.data)
    assert downloaded.startswith(pickle.PROTO)


def test_non_utf8_writes_are_stored_as_binary(tmp_path):
    cache = _cache(tmp_path)
    resources = CacheResources(cache)

    entry = asyncio.run(resources.write("raw", b"\xff\xfe"))

    assert entry.attributes["data_type"] == "binary"
    assert cache.get("raw") == b"\xff\xfe"


def test_rows_carry_type_tier_age_and_a_summary(tmp_path):
    cache = _cache(tmp_path)
    cache.hot.set_json("flags", {"beta": True})
    cache.set_binary("blob", b"\x00\x01")
    resources = CacheResources(cache)

    rows = {e.id: e for e in asyncio.run(resources.list()).entries}

    assert rows["flags"].attributes["summary"] == '{"beta": true}'
    assert (rows["flags"].attributes["data_type"], rows["flags"].attributes["tier"]) == (
        "json",
        TIER_HOT,
    )
    assert rows["alpha"].attributes["summary"] == "first value"
    assert rows["alpha"].modified == rows["alpha"].attributes["created_at"]
    assert "summary" not in rows["blob"].attributes
    assert rows["blob"].size == 2


def test_opening_an_entry_names_every_tier_holding_it(tmp_path):
    cache = _cache(tmp_path)
    cache.hot.set_text("alpha", "hot copy")
    resources = CacheResources(cache)

    detail = asyncio.run(resources.read("alpha"))

    assert detail.entry.attributes["tiers"] == f"{TIER_HOT}, {TIER_COLD}"
    assert asyncio.run(resources.stat("beta")).attributes["tiers"] == TIER_COLD


def test_json_entries_come_back_structured(tmp_path):
    cache = _cache(tmp_path)
    cache.set_json("config", {"limits": [1, 2], "on": True})

    detail = asyncio.run(CacheResources(cache).read("config"))

    assert detail.view == {"type": "json", "value": {"limits": [1, 2], "on": True}}
    assert asyncio.run(CacheResources(cache).read("alpha")).view is None


def test_replacing_a_json_entry_keeps_it_json_and_validates(tmp_path):
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import InvalidResource

    cache = _cache(tmp_path)
    cache.set_json("config", {"on": True})
    resources = CacheResources(cache)

    asyncio.run(resources.write("config", b'{"on": false}'))

    assert cache.get_entry("config").cached.data_type.value == "json"
    assert cache.get("config") == {"on": False}
    with pytest.raises(InvalidResource, match="does not parse"):
        asyncio.run(resources.write("config", b"not json"))
    assert cache.get("config") == {"on": False}
    # A new key with JSON-looking text stays text.
    asyncio.run(resources.write("fresh", b'{"a": 1}'))
    assert cache.get_entry("fresh").cached.data_type.value == "text"


def test_search_keeps_keys_containing_the_text(tmp_path):
    cache = _cache(tmp_path)
    cache.hot.set_text("model:gpt", "x")
    cache.set_text("embedding:MODEL-v2", "y")
    resources = CacheResources(cache)

    page = asyncio.run(resources.list(query="model"))

    assert resources.capabilities.search is True
    assert [e.id for e in page.entries] == ["embedding:MODEL-v2", "model:gpt"]
    assert page.next_cursor is None
