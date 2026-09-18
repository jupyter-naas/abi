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
