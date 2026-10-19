"""``abi chat`` and ``abi run script`` reach the data services after boot.

The data services deny a call with no caller; the terminal acts as the engine
it loads (``as_local_operator``). Engine loading and the agent are faked: what is
checked is that the work after boot can still query an enforcing service.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from click.testing import CliRunner
from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.event import local_identity
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.enforcement import internal_call
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.iam_catalog import CATALOG
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

from naas_abi_cli.cli.local_operator import as_local_operator

QUERY = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"
# The graph every triple store bootstraps: the engine reads it.
SCHEMA = "http://ontology.naas.ai/graph/schema"
seen: dict[str, object] = {}


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


def _store(tmp_path: Path) -> TripleStoreService:
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with internal_call():
        iam.register_catalog(CATALOG)
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "oxigraph")))
    store.set_services(IEngine.Services(iam=iam, bus=_Bus()))  # type: ignore[arg-type]
    return store


class _Engine:
    store: TripleStoreService

    def __init__(self, *_args, **_kwargs) -> None:
        self.configuration = type("C", (), {"default_agent": "demo Agent"})()
        self.modules = {"demo": type("M", (), {"agents": [_Agent]})()}

    def load(self, *_args, **_kwargs) -> None:
        return None


class _Agent:
    @classmethod
    def New(cls):
        return cls()


@pytest.fixture
def engine(tmp_path, monkeypatch):
    _Engine.store = _store(tmp_path)
    monkeypatch.setattr("naas_abi_core.engine.Engine.Engine", _Engine)
    # The package exports a ``run`` group that hides the ``run`` module.
    monkeypatch.setattr(
        importlib.import_module("naas_abi_cli.cli.run"), "Engine", _Engine
    )
    seen.clear()
    return _Engine


def test_a_script_queries_as_the_engine(engine, tmp_path):
    run_script = importlib.import_module("naas_abi_cli.cli.run").run_script

    script = tmp_path / "script.py"
    script.write_text(
        "from naas_abi_cli.cli.local_operator_test import _Engine, seen, QUERY\n"
        "from naas_abi_core.engine.call_context import current_call_context\n"
        "seen['rows'] = [str(r[0]) for r in _Engine.store.query(QUERY)]\n"
        "seen['actor'] = current_call_context().principal.name\n"
    )
    result = CliRunner().invoke(run_script, [str(script)], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert seen == {"rows": [SCHEMA], "actor": "engine"}
    # Outside the command, the terminal is anonymous again.
    assert current_call_context().principal.kind == "anonymous"


def test_a_chat_agent_queries_as_the_engine(engine, monkeypatch):
    chat = importlib.import_module("naas_abi_cli.cli.chat").chat

    def run_agent(agent):
        seen["rows"] = [str(r[0]) for r in _Engine.store.query(QUERY)]
        seen["actor"] = current_call_context().principal.name

    monkeypatch.setattr("naas_abi_core.apps.terminal_agent.main.run_agent", run_agent)
    result = CliRunner().invoke(chat, ["demo", "_Agent"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert seen == {"rows": [SCHEMA], "actor": "engine"}


def test_anonymous_work_after_boot_is_denied(engine):
    from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions

    # What the commands guard against: the same query with no caller.
    with pytest.raises(Exceptions.GraphNotFoundError):
        _Engine.store.query("SELECT * WHERE { GRAPH <urn:g> { ?s ?p ?o } }")


def test_terminal_work_runs_as_the_engine_for_its_git_author(monkeypatch):
    monkeypatch.setattr(local_identity, "git_user_email", lambda: "Ada@Example.com")
    with as_local_operator():
        context = current_call_context()
        assert context.principal.name == "engine"
        assert context.user is not None
        assert context.user.id == local_identity.email_actor_id("ada@example.com")
        assert context.triggered_via == "cli"
    assert current_call_context().principal.kind == "anonymous"


def test_without_a_git_author_it_runs_as_the_engine_for_nobody(monkeypatch):
    monkeypatch.setattr(local_identity, "git_user_email", lambda: None)
    with as_local_operator():
        context = current_call_context()
        assert context.principal.name == "engine" and context.user is None
