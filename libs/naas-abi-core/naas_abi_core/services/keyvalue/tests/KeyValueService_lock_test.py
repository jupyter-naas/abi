from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
    PythonAdapter,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import KVLockTimeoutError
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


def _kv(persistence_path: str | None = None) -> KeyValueService:
    return KeyValueService(PythonAdapter(persistence_path=persistence_path))


def test_lock_acquire_and_release() -> None:
    kv = _kv()
    key = f"lock:kv:{uuid4()}"
    with kv.lock(key, ttl=5, timeout=1):
        assert kv.exists(key) is True
    assert kv.exists(key) is False


def test_lock_released_on_exception() -> None:
    kv = _kv()
    key = f"lock:kv:{uuid4()}"
    with pytest.raises(RuntimeError, match="boom"), kv.lock(key, ttl=5, timeout=1):
        raise RuntimeError("boom")
    assert kv.exists(key) is False
    with kv.lock(key, ttl=5, timeout=0):
        pass


def test_lock_times_out_while_held() -> None:
    kv = _kv()
    key = f"lock:kv:{uuid4()}"
    with kv.lock(key, ttl=5, timeout=1):
        with (
            pytest.raises(KVLockTimeoutError) as exc,
            kv.lock(key, ttl=5, timeout=0.15, retry_delay=0.02),
        ):
            raise AssertionError("second holder should not enter")
        assert exc.value.key == key
        assert exc.value.attempts >= 1


def test_lock_waits_then_succeeds_after_release() -> None:
    kv = _kv()
    key = f"lock:kv:{uuid4()}"
    entered: list[str] = []
    holding = Event()

    def holder() -> None:
        with kv.lock(key, ttl=5, timeout=1):
            entered.append("holder")
            holding.set()
            time.sleep(0.08)

    def waiter() -> None:
        assert holding.wait(timeout=1)
        with kv.lock(key, ttl=5, timeout=1, retry_delay=0.02):
            entered.append("waiter")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(holder)
        second = pool.submit(waiter)
        first.result()
        second.result()
    assert entered == ["holder", "waiter"]


def test_lock_token_does_not_release_another_holder() -> None:
    kv = _kv()
    key = f"lock:kv:{uuid4()}"
    with kv.lock(key, ttl=5, timeout=1):
        assert kv.delete_if_value_matches(key, b"not-the-token") is False
        assert kv.exists(key) is True


def test_lock_serializes_two_sqlite_connections(tmp_path) -> None:
    db = str(tmp_path / "kv-lock.sqlite3")
    key = f"lock:kv:{uuid4()}"
    kv_a = _kv(persistence_path=db)
    kv_b = _kv(persistence_path=db)
    critical: list[str] = []

    def worker(name: str, kv: KeyValueService) -> None:
        with kv.lock(key, ttl=5, timeout=2, retry_delay=0.02):
            critical.append(f"{name}-in")
            time.sleep(0.05)
            critical.append(f"{name}-out")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, "a", kv_a), pool.submit(worker, "b", kv_b)]
        for future in futures:
            future.result()

    assert critical in (
        ["a-in", "a-out", "b-in", "b-out"],
        ["b-in", "b-out", "a-in", "a-out"],
    )


def test_lock_rejects_non_positive_ttl() -> None:
    kv = _kv()
    with pytest.raises(ValueError, match="ttl"), kv.lock("k", ttl=0):
        pass
