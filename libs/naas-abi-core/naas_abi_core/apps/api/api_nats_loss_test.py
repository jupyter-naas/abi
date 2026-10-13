"""The API process stops when NATS is gone for good, so its supervisor restarts it."""

import sys
import types

import pytest
from naas_abi_core.apps.api import api as api_module
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ApiConfiguration,
)
from naas_abi_sdk import lifeline


@pytest.fixture
def opted_in(monkeypatch) -> list[bool]:
    """Starts the API without serving; records whether it opted in."""
    calls: list[bool] = []

    def exit_on_connection_loss(*args, **kwargs):
        calls.append(True)
        return lambda: None

    monkeypatch.setitem(
        sys.modules, "uvicorn", types.SimpleNamespace(run=lambda **_: None)
    )
    monkeypatch.setattr(api_module, "get_app", lambda: "app")
    monkeypatch.setattr(lifeline, "exit_on_connection_loss", exit_on_connection_loss)
    return calls


def _start(monkeypatch, *, reload: bool, nats: bool) -> None:
    monkeypatch.setattr(
        api_module, "api_runtime_configuration", ApiConfiguration(reload=reload)
    )
    monkeypatch.setattr(api_module, "_nats_mode", nats)
    api_module.api()


def test_a_nats_engine_stops_when_nats_is_gone_for_good(monkeypatch, opted_in):
    _start(monkeypatch, reload=False, nats=True)

    assert opted_in == [True]


def test_with_reload_a_loss_is_only_logged(monkeypatch, opted_in):
    # The reloader would not restart a worker that exits.
    _start(monkeypatch, reload=True, nats=True)

    assert opted_in == []


def test_without_nats_nothing_changes(monkeypatch, opted_in):
    _start(monkeypatch, reload=False, nats=False)

    assert opted_in == []
