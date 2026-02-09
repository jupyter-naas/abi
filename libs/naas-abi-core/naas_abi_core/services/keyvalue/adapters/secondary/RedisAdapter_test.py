import os
import time
from uuid import uuid4

import pytest

pytest.importorskip("redis")

from naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter import RedisAdapter
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError
from naas_abi_core.services.keyvalue.tests.kv__secondary_adapter__generic_test import (
    GenericKVSecondaryAdapterTest,
)


def _redis_config_available() -> bool:
    return bool(os.getenv("REDIS_URL"))


class TestRedisAdapter(GenericKVSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return RedisAdapter

    @pytest.fixture
    def adapter(self):
        if not _redis_config_available():
            pytest.skip("Redis integration tests require REDIS_URL")

        adapter = RedisAdapter(redis_url=os.getenv("REDIS_URL"))

        yield adapter

    def test_set_get_exists_delete(self, adapter):
        key = f"naas-abi-core:kv:test:{uuid4()}"
        value = b"hello"

        adapter.set(key, value)
        try:
            assert adapter.exists(key) is True
            assert adapter.get(key) == value

            adapter.delete(key)
            assert adapter.exists(key) is False

            with pytest.raises(KVNotFoundError):
                adapter.get(key)
        finally:
            try:
                if adapter.exists(key):
                    adapter.delete(key)
            except KVNotFoundError:
                pass

    def test_set_with_ttl_expires(self, adapter):
        key = f"naas-abi-core:kv:ttl:{uuid4()}"
        value = b"hello-ttl"

        adapter.set(key, value, ttl=1)
        try:
            assert adapter.exists(key) is True

            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and adapter.exists(key):
                time.sleep(0.1)

            assert adapter.exists(key) is False
            with pytest.raises(KVNotFoundError):
                adapter.get(key)
        finally:
            try:
                if adapter.exists(key):
                    adapter.delete(key)
            except KVNotFoundError:
                pass

    def test_set_if_not_exists(self, adapter):
        key = f"naas-abi-core:kv:nx:{uuid4()}"
        first = b"first-value"
        second = b"second-value"

        try:
            assert adapter.set_if_not_exists(key, first, ttl=5) is True
            assert adapter.set_if_not_exists(key, second, ttl=5) is False
            assert adapter.get(key) == first
        finally:
            try:
                if adapter.exists(key):
                    adapter.delete(key)
            except KVNotFoundError:
                pass

    def test_set_if_not_exists_with_ttl_expires(self, adapter):
        key = f"naas-abi-core:kv:nx-ttl:{uuid4()}"
        value = b"nx-ttl"

        try:
            assert adapter.set_if_not_exists(key, value, ttl=1) is True
            assert adapter.exists(key) is True

            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and adapter.exists(key):
                time.sleep(0.1)

            assert adapter.exists(key) is False
            assert adapter.set_if_not_exists(key, value, ttl=1) is True
        finally:
            try:
                if adapter.exists(key):
                    adapter.delete(key)
            except KVNotFoundError:
                pass

    def test_delete_if_value_matches(self, adapter):
        key = f"naas-abi-core:kv:cmp-del:{uuid4()}"
        token = f"token:{uuid4()}".encode("utf-8")
        other = f"token:{uuid4()}".encode("utf-8")

        adapter.set(key, token, ttl=5)
        try:
            assert adapter.delete_if_value_matches(key, other) is False
            assert adapter.exists(key) is True
            assert adapter.delete_if_value_matches(key, token) is True
            assert adapter.exists(key) is False
        finally:
            try:
                if adapter.exists(key):
                    adapter.delete(key)
            except KVNotFoundError:
                pass
