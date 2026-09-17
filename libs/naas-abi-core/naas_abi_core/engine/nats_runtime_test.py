from unittest.mock import AsyncMock, MagicMock

import pytest
from naas_abi_core.engine import nats_runtime


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Every test starts and ends with no shared connection/loop -- mirrors
    Agent.py's _reset_shared_checkpointer_for_tests pattern for the same
    kind of module-level shared resource."""
    nats_runtime.close()
    yield
    nats_runtime.close()


def test_run_coro_returns_the_coroutine_result():
    async def _one():
        return 1

    assert nats_runtime.run_coro(_one()) == 1


def test_get_connection_reuses_the_existing_connection_for_the_same_url(monkeypatch):
    connect = AsyncMock(
        return_value=MagicMock(is_connected=True, close=AsyncMock())
    )
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)

    first = nats_runtime.get_connection("nats://127.0.0.1:4222")
    second = nats_runtime.get_connection("nats://127.0.0.1:4222")

    assert first is second
    connect.assert_awaited_once_with("nats://127.0.0.1:4222")


def test_get_connection_reconnects_when_the_url_changes(monkeypatch):
    old_conn = MagicMock(is_connected=True, close=AsyncMock())
    new_conn = MagicMock(is_connected=True, close=AsyncMock())
    connect = AsyncMock(side_effect=[old_conn, new_conn])
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)

    first = nats_runtime.get_connection("nats://127.0.0.1:4222")
    second = nats_runtime.get_connection("nats://127.0.0.1:4223")

    assert first is old_conn
    assert second is new_conn
    old_conn.close.assert_awaited_once()
    assert connect.await_count == 2


def test_get_connection_reconnects_if_the_existing_connection_died(monkeypatch):
    dead_conn = MagicMock(is_connected=False, close=AsyncMock())
    fresh_conn = MagicMock(is_connected=True, close=AsyncMock())
    connect = AsyncMock(side_effect=[dead_conn, fresh_conn])
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)

    first = nats_runtime.get_connection("nats://127.0.0.1:4222")
    second = nats_runtime.get_connection("nats://127.0.0.1:4222")

    assert first is dead_conn
    assert second is fresh_conn
    assert connect.await_count == 2
