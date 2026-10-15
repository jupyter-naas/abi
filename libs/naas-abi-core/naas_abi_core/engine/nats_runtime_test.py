import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from naas_abi_core.engine import nats_runtime
from naas_abi_sdk import lifeline


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
        return_value=MagicMock(is_connected=True, is_closed=False, close=AsyncMock())
    )
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)

    first = nats_runtime.get_connection("nats://127.0.0.1:4222")
    second = nats_runtime.get_connection("nats://127.0.0.1:4222")

    assert first is second
    connect.assert_awaited_once_with(
        "nats://127.0.0.1:4222",
        name=nats_runtime.connection_name("abi-engine"),
        closed_cb=ANY,
    )


def test_the_shared_connection_closing_for_good_stops_the_process(monkeypatch):
    connect = AsyncMock(
        return_value=MagicMock(is_connected=True, is_closed=False, close=AsyncMock())
    )
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)
    stops: list[str] = []
    restore = lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    try:
        nats_runtime.get_connection("nats://127.0.0.1:4222")
        # nats-py calls closed_cb once it gives up reconnecting.
        nats_runtime.run_coro(connect.await_args.kwargs["closed_cb"]())
    finally:
        restore()

    assert stops == ["stop"]


def test_closing_the_shared_connection_is_not_a_loss(monkeypatch):
    connect = AsyncMock(
        return_value=MagicMock(is_connected=True, is_closed=False, close=AsyncMock())
    )
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)
    stops: list[str] = []
    restore = lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    try:
        nats_runtime.get_connection("nats://127.0.0.1:4222")
        nats_runtime.close()
        asyncio.run(connect.await_args.kwargs["closed_cb"]())
    finally:
        restore()

    assert stops == []


def test_get_connection_reconnects_when_the_url_changes(monkeypatch):
    old_conn = MagicMock(is_connected=True, is_closed=False, close=AsyncMock())
    new_conn = MagicMock(is_connected=True, is_closed=False, close=AsyncMock())
    connect = AsyncMock(side_effect=[old_conn, new_conn])
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)

    first = nats_runtime.get_connection("nats://127.0.0.1:4222")
    second = nats_runtime.get_connection("nats://127.0.0.1:4223")

    assert first is old_conn
    assert second is new_conn
    old_conn.close.assert_awaited_once()
    assert connect.await_count == 2


def test_get_connection_reconnects_if_the_existing_connection_died(monkeypatch):
    dead_conn = MagicMock(is_connected=False, is_closed=False, close=AsyncMock())
    fresh_conn = MagicMock(is_connected=True, is_closed=False, close=AsyncMock())
    connect = AsyncMock(side_effect=[dead_conn, fresh_conn])
    monkeypatch.setattr(nats_runtime.nats, "connect", connect)

    first = nats_runtime.get_connection("nats://127.0.0.1:4222")
    second = nats_runtime.get_connection("nats://127.0.0.1:4222")

    assert first is dead_conn
    assert second is fresh_conn
    assert connect.await_count == 2
