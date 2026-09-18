"""Tests for Engine.shutdown() -- graceful teardown of whatever load()
started over NATS.

Constructs a bare ``Engine`` via ``__new__`` rather than the real
constructor: ``Engine()`` requires a fully valid ``EngineConfiguration``
(and its own pre-existing test fixture is broken -- see ``Engine_test.py``
and the dev log), which shutdown()'s own logic has no need of. Only the
two attributes shutdown() actually touches
(``_Engine__nats_primary_adapters``, set via its name-mangled attribute
since it's a private field) need to exist.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from naas_abi_core.engine.Engine import Engine


def _bare_engine(primaries: list) -> Engine:
    engine = Engine.__new__(Engine)
    engine._Engine__nats_primary_adapters = primaries  # type: ignore[attr-defined]
    return engine


def test_shutdown_is_a_noop_when_nats_was_never_configured(monkeypatch):
    close = MagicMock()
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", close)
    engine = _bare_engine([])

    engine.shutdown()  # must not raise

    close.assert_called_once()


def test_shutdown_stops_every_started_primary_adapter(monkeypatch):
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    close = MagicMock()
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", close)

    primary_a = MagicMock()
    primary_a.stop = AsyncMock()
    primary_b = MagicMock()
    primary_b.stop = AsyncMock()
    engine = _bare_engine([primary_a, primary_b])

    engine.shutdown()

    assert run_coro.call_count == 2
    close.assert_called_once()
    # Cleared so a second call doesn't try to stop them again.
    assert engine._Engine__nats_primary_adapters == []  # type: ignore[attr-defined]


def test_shutdown_closes_the_shared_connection_after_stopping_primaries(monkeypatch):
    order: list[str] = []
    run_coro = MagicMock(
        side_effect=lambda coro, *a, **k: (order.append("stop_primary"), coro.close())
    )
    close = MagicMock(side_effect=lambda: order.append("close_connection"))
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", close)

    primary = MagicMock()
    primary.stop = AsyncMock()
    engine = _bare_engine([primary])

    engine.shutdown()

    assert order == ["stop_primary", "close_connection"]


def test_shutdown_is_safe_when_a_primary_fails_to_stop(monkeypatch):
    """A slow/broken primary must never block the rest of shutdown or
    crash the process on the way out."""

    def _boom(coro, *a, **k):
        coro.close()
        raise RuntimeError("connection already gone")

    run_coro = MagicMock(side_effect=_boom)
    close = MagicMock()
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", close)

    broken = MagicMock()
    broken.stop = AsyncMock()
    healthy = MagicMock()
    healthy.stop = AsyncMock()
    engine = _bare_engine([broken, healthy])

    engine.shutdown()  # must not raise

    assert run_coro.call_count == 2
    close.assert_called_once()


def test_shutdown_can_be_called_more_than_once(monkeypatch):
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    close = MagicMock()
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", close)

    primary = MagicMock()
    primary.stop = AsyncMock()
    engine = _bare_engine([primary])

    engine.shutdown()
    engine.shutdown()  # must not re-stop anything or raise

    assert run_coro.call_count == 1
    assert close.call_count == 2
