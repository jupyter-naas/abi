import time
from abc import ABC, abstractmethod
from uuid import uuid4

import pytest
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError


class GenericKVSecondaryAdapterTest(ABC):
    """Every adapter's test subclasses this with ``adapter_class`` and ``adapter``
    fixtures (``adapter``: a working instance; it may hold other keys)."""

    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        assert callable(getattr(adapter_class, "get", None))
        assert callable(getattr(adapter_class, "set", None))
        assert callable(getattr(adapter_class, "set_if_not_exists", None))
        assert callable(getattr(adapter_class, "delete", None))
        assert callable(getattr(adapter_class, "delete_if_value_matches", None))
        assert callable(getattr(adapter_class, "exists", None))
        assert callable(getattr(adapter_class, "list_keys", None))
        assert callable(getattr(adapter_class, "get_ttl", None))

    # --- list_keys -------------------------------------------------------------

    @staticmethod
    def _seed(adapter) -> tuple[str, list[str]]:
        # A unique prefix: shared backends (Redis, NATS) may hold other keys.
        prefix = f"naas-abi-core:kv:list:{uuid4()}:"
        keys = [f"{prefix}{name}" for name in ("c", "a/x", "b", "a/y", "é")]
        for key in keys:
            adapter.set(key, b"v")
        return prefix, sorted(keys)

    def test_list_keys_returns_keys_under_a_prefix_in_order(self, adapter):
        prefix, keys = self._seed(adapter)

        page = adapter.list_keys(prefix, limit=100)

        assert page.keys == tuple(keys)
        assert page.next_after is None
        assert adapter.list_keys(f"{prefix}a/", limit=100).keys == (
            f"{prefix}a/x",
            f"{prefix}a/y",
        )

    def test_list_keys_pages_strictly_after_the_cursor(self, adapter):
        prefix, keys = self._seed(adapter)

        seen, after = [], None
        for _ in range(10):
            page = adapter.list_keys(prefix, limit=2, after=after)
            assert len(page.keys) <= 2
            seen += page.keys
            after = page.next_after
            if after is None:
                break

        assert seen == keys
        assert adapter.list_keys(prefix, limit=100, after=keys[-1]).keys == ()

    def test_list_keys_skips_expired_and_deleted_keys(self, adapter):
        prefix = f"naas-abi-core:kv:list-ttl:{uuid4()}:"
        adapter.set(f"{prefix}stays", b"v")
        adapter.set(f"{prefix}expires", b"v", ttl=1)
        adapter.set(f"{prefix}deleted", b"v")
        adapter.delete(f"{prefix}deleted")

        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and adapter.exists(f"{prefix}expires"):
            time.sleep(0.1)

        assert adapter.list_keys(prefix, limit=100).keys == (f"{prefix}stays",)

    # --- get_ttl -----------------------------------------------------------------

    def test_get_ttl_reports_remaining_seconds(self, adapter):
        key = f"naas-abi-core:kv:ttl-read:{uuid4()}"
        adapter.set(key, b"v", ttl=60)
        forever = f"{key}:forever"
        adapter.set(forever, b"v")

        assert 0 < adapter.get_ttl(key) <= 60
        assert adapter.get_ttl(forever) is None
        with pytest.raises(KVNotFoundError):
            adapter.get_ttl(f"{key}:missing")
