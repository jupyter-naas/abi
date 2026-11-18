"""How api() runs uvicorn: no reload by default, a log level of its own."""

import sys
import types

import pytest
from naas_abi_core.apps.api import api as api_module
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ApiConfiguration,
)


@pytest.fixture
def uvicorn_run(monkeypatch) -> list[dict]:
    """Starts the API without serving; records what uvicorn.run was given."""
    runs: list[dict] = []
    monkeypatch.setitem(
        sys.modules, "uvicorn", types.SimpleNamespace(run=lambda **kw: runs.append(kw))
    )
    monkeypatch.setattr(api_module, "get_app", lambda: "app")
    monkeypatch.setattr(api_module, "_nats_mode", False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    return runs


def _start(monkeypatch, **api_settings) -> None:
    monkeypatch.setattr(
        api_module, "api_runtime_configuration", ApiConfiguration(**api_settings)
    )
    api_module.api()


def test_reload_is_off_by_default():
    assert ApiConfiguration().reload is False


def test_by_default_the_app_is_served_without_reload_at_info(monkeypatch, uvicorn_run):
    _start(monkeypatch)

    (run,) = uvicorn_run
    assert run["reload"] is False
    assert run["app"] == "app"
    assert run["log_level"] == "info"


def test_reload_does_not_force_debug(monkeypatch, uvicorn_run):
    _start(monkeypatch, reload=True)

    (run,) = uvicorn_run
    assert run["reload"] is True
    assert run["app"] == "naas_abi_core.apps.api.api:get_app"
    assert run["log_level"] == "info"


def test_the_engine_log_level_does_not_reach_uvicorn(monkeypatch, uvicorn_run):
    # LOG_LEVEL=DEBUG in the local stacks: uvicorn at debug logs session cookies.
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    _start(monkeypatch, reload=True)

    assert uvicorn_run[0]["log_level"] == "info"


def test_the_configured_log_level_is_used(monkeypatch, uvicorn_run):
    _start(monkeypatch, log_level="WARNING")

    assert uvicorn_run[0]["log_level"] == "warning"


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("WARN", "warning"),
        ("SUCCESS", "info"),
        ("trace", "trace"),
        (" Error ", "error"),
        ("loud", "info"),
        ("", "info"),
        (None, "info"),
    ],
)
def test_levels_map_to_uvicorn_levels(value, level):
    assert api_module._uvicorn_log_level(value) == level
