"""Tests for the FastAPI app's shutdown lifespan hook -- graceful teardown
of the engine's NATS primary adapters (see Engine.shutdown()).

Uses TestClient's context-manager form specifically because that's what
actually drives FastAPI's lifespan startup/shutdown events; a bare
``TestClient(app)`` (no ``with``) never triggers shutdown at all.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from naas_abi_core.apps.api import api as api_module


def test_shutdown_is_a_noop_when_the_engine_was_never_loaded(monkeypatch):
    """The common case for a request that never touches a protected
    endpoint: LazyEngine._engine stays None, so shutdown must not force a
    whole Engine() to be constructed and loaded just to tear it down."""
    monkeypatch.setattr(api_module.engine, "_engine", None)

    with TestClient(api_module.app):
        pass  # lifespan startup + shutdown both run here

    assert api_module.engine._engine is None


def test_shutdown_calls_engine_shutdown_when_the_engine_was_loaded(monkeypatch):
    fake_engine = MagicMock()
    monkeypatch.setattr(api_module.engine, "_engine", fake_engine)

    with TestClient(api_module.app):
        pass

    fake_engine.shutdown.assert_called_once()


def test_event_handlers_added_by_modules_still_run_under_the_custom_lifespan(
    monkeypatch,
):
    """Modules attach to this app with ``app.add_event_handler(...)`` -- Nexus
    does exactly that in ``naas_abi/apps/nexus/apps/api/app/main.py``
    (``_register_startup_handlers``) to run its migrations and seeds.

    Passing ``lifespan=`` to FastAPI replaces Starlette's ``_DefaultLifespan``,
    which is the only thing that would otherwise call ``router.startup()`` /
    ``router.shutdown()``; if our lifespan forgets to drive them, every such
    handler is silently skipped (no warning) and Nexus boots without tables.
    """
    monkeypatch.setattr(api_module.engine, "_engine", None)
    calls: list[str] = []

    def on_startup() -> None:
        calls.append("startup")

    async def on_shutdown() -> None:
        calls.append("shutdown")

    api_module.app.add_event_handler("startup", on_startup)
    api_module.app.add_event_handler("shutdown", on_shutdown)
    try:
        with TestClient(api_module.app):
            assert calls == ["startup"]
        assert calls == ["startup", "shutdown"]
    finally:
        api_module.app.router.on_startup.remove(on_startup)
        api_module.app.router.on_shutdown.remove(on_shutdown)


def test_module_shutdown_handlers_run_before_the_engine_is_torn_down(monkeypatch):
    """A module's shutdown hook may still need engine services (triple store,
    object storage, ...), so the engine -- their dependency -- must be the
    last thing torn down."""
    order: list[str] = []
    fake_engine = MagicMock()
    fake_engine.shutdown.side_effect = lambda: order.append("engine")
    monkeypatch.setattr(api_module.engine, "_engine", fake_engine)

    def on_shutdown() -> None:
        order.append("module")

    api_module.app.add_event_handler("shutdown", on_shutdown)
    try:
        with TestClient(api_module.app):
            pass
    finally:
        api_module.app.router.on_shutdown.remove(on_shutdown)

    assert order == ["module", "engine"]
