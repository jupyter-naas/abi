"""Workspace agent sync with agents published by remote modules (NATS discovery)."""

from __future__ import annotations

import asyncio
from dataclasses import fields, replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
    agents__primary_adapter__FastAPI as sync,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    REMOTE_PROVIDER,
    RemoteAgent,
    RemoteAgentSuggestion,
)

ZEN = "zen.agents.ZenAgent/ZenAgent"
RESEARCHER = RemoteAgent("acme.research", "Researcher", "Answers research questions.")
WRITER = RemoteAgent("acme.writing", "Writer")


class _ZenAgent:
    name = "Zen"


class _Agents:
    """The AgentService subset sync uses, in memory."""

    def __init__(self, records: list[AgentRecord]) -> None:
        self.records = {r.id: r for r in records}
        self.deleted: list[str] = []

    async def list_workspace_agents(self, workspace_id):
        return list(self.records.values())

    async def create_agent(self, data):
        now = datetime(2026, 10, 1)
        record = AgentRecord(
            id=f"a-{len(self.records) + 1}",
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description or "",
            class_name=data.class_name,
            module_path=data.module_path,
            system_prompt=data.system_prompt,
            model_id=data.model_id,
            provider=data.provider,
            logo_url=data.logo_url,
            created_at=now,
            updated_at=now,
        )
        self.records[record.id] = record
        return record

    async def update_agent(self, agent_id, updates):
        known = {f.name for f in fields(AgentRecord)}
        changes = {
            f.name: getattr(updates, f.name)
            for f in fields(updates)
            if getattr(updates, f.name) is not None and f.name in known
        }
        self.records[agent_id] = replace(self.records[agent_id], **changes)
        return self.records[agent_id]

    async def delete_agent(self, agent_id):
        self.deleted.append(agent_id)
        return self.records.pop(agent_id, None) is not None


def _record(
    agent_id: str,
    class_name: str,
    *,
    provider: str = "abi",
    default: bool = False,
):
    now = datetime(2026, 10, 1)
    return AgentRecord(
        id=agent_id,
        workspace_id="ws",
        name=class_name.rsplit("/", 1)[-1],
        description="",
        class_name=class_name,
        module_path=class_name.split("/", 1)[0],
        system_prompt=None,
        model_id=None,
        provider=provider,
        logo_url=None,
        created_at=now,
        updated_at=now,
        is_default=default,
    )


class _NoSession:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def seed(monkeypatch):
    """Set the workspace seed: None (no config entry) or an ``agents:`` list."""
    state = {"seed": None}

    async def slug(workspace_id):
        return "ws"

    monkeypatch.setattr(sync, "_workspace_slug", slug)

    async def catalog_seed(workspace_id):
        return state["seed"]

    monkeypatch.setattr(sync, "_workspace_catalog_seed", catalog_seed)
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.core.database.AsyncSessionLocal",
        lambda: _NoSession(),
    )
    monkeypatch.setattr(sync, "_get_engine_default_agent_class_name", lambda: ZEN)

    def set_seed(agents):
        state["seed"] = {"agents": agents}

    return set_seed


def _sync(agents: _Agents, remote_agents):
    return asyncio.run(
        sync._reconcile_workspace_agents(
            agents,
            "ws",
            list(agents.records.values()),
            {ZEN: _ZenAgent},
            remote_agents=remote_agents,
        )
    )


def _by_class(records):
    return {r.class_name: r for r in records}


def test_discovered_agents_are_created_with_no_on_off_state(seed):
    agents = _Agents([_record("zen", ZEN, default=True)])

    result = _by_class(_sync(agents, [RESEARCHER, WRITER]))

    researcher = result[RESEARCHER.key]
    assert researcher.provider == REMOTE_PROVIDER
    assert (researcher.name, researcher.description) == (
        "Researcher",
        "Answers research questions.",
    )
    assert researcher.module_path == "acme.research"
    assert WRITER.key in result
    assert result[ZEN].is_default
    assert not hasattr(researcher, "enabled")


def test_an_agents_seed_no_longer_narrows_the_roster(seed):
    """Who uses an agent is IAM's: the seed's ``agents:`` list creates or hides
    no row (its ``default_agent`` still marks the default)."""
    seed(["zen ZenAgent", "acme.research Researcher"])
    agents = _Agents([_record("zen", ZEN)])

    result = _by_class(_sync(agents, [RESEARCHER, WRITER]))

    assert {RESEARCHER.key, WRITER.key, ZEN} <= set(result)
    assert result[ZEN].is_default


def test_an_unavailable_remote_agent_is_kept_not_deleted(seed):
    agents = _Agents(
        [_record("zen", ZEN, default=True), _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER)]
    )

    result = _by_class(_sync(agents, []))

    assert agents.deleted == []
    assert RESEARCHER.key in result


def test_unknown_discovery_state_leaves_remote_rows_alone(seed):
    agents = _Agents(
        [_record("zen", ZEN, default=True), _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER)]
    )

    result = _by_class(_sync(agents, None))

    assert RESEARCHER.key in result
    assert agents.deleted == []


def test_stale_in_process_rows_are_still_pruned(seed):
    agents = _Agents(
        [_record("zen", ZEN, default=True), _record("old", "gone.module.OldAgent/OldAgent")]
    )

    _sync(agents, [])

    assert agents.deleted == ["old"]


def test_remote_agents_show_no_model_unless_one_is_assigned():
    remote = _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER)

    assert sync._resolve_agent_model_id(remote) is None
    assert sync._resolve_agent_model_id(replace(remote, model_id="gpt-5.5")) == "gpt-5.5"


def test_discovery_errors_mean_unknown_not_empty(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote import factory

    class _Broken:
        async def list_agents(self):
            raise ConnectionError("nats down")

    monkeypatch.setattr(factory, "get_remote_agent_directory", lambda: _Broken())

    assert asyncio.run(sync._discovered_remote_agents()) is None


def test_the_listing_leaves_out_remote_agents_whose_module_is_not_ready(monkeypatch):
    zen = _record("zen", ZEN, default=True)
    researcher = _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER)
    writer = _record("w", WRITER.key, provider=REMOTE_PROVIDER)

    async def discovered():
        return [RESEARCHER]

    monkeypatch.setattr(sync, "_discovered_remote_agents", discovered)
    assert [a.id for a in asyncio.run(sync.served_agents([zen, researcher, writer]))] == [
        "zen",
        "r",
    ]

    async def unknown():
        return None

    # Discovery cannot be read: every row is kept.
    monkeypatch.setattr(sync, "_discovered_remote_agents", unknown)
    assert len(asyncio.run(sync.served_agents([zen, researcher, writer]))) == 3


@pytest.mark.asyncio
async def test_an_update_changes_the_configuration_only(team):
    from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentUpdateInput

    captured = []

    class _Service:
        async def get_agent(self, agent_id):
            return replace(
                _record(agent_id, RESEARCHER.key, provider=REMOTE_PROVIDER),
                workspace_id="ws-1",
            )

        async def update_agent(self, agent_id, updates):
            captured.append(updates)
            return _record(agent_id, RESEARCHER.key, provider=REMOTE_PROVIDER)

    admin = SimpleNamespace(id="admin")
    await sync.update_agent("r", AgentUpdateInput(name="R", model="gpt-5.5"), admin, _Service())

    assert (captured[0].name, captured[0].model_id) == ("R", "gpt-5.5")
    assert not hasattr(captured[0], "enabled")


# Presentation: what the module publishes is what the workspace shows.

PRESENTED = RemoteAgent(
    "acme.accounts",
    "ACME_Account_Director",
    "Answers from the ACME account graph.",
    display_name="ACME Account Director",
    avatar_url="/modules/acme/assets/public/acme.png",
    suggestions=(
        RemoteAgentSuggestion("State of the account", "Brief me on ACME.", "One screen"),
        RemoteAgentSuggestion("Who leads?", "Who leads the ACME account?"),
    ),
)


def test_remote_rows_show_the_published_name_avatar_and_suggestions(monkeypatch):
    monkeypatch.setattr(sync, "public_api_host", lambda: "https://api.example.com")
    row = _record("r", PRESENTED.key, provider=REMOTE_PROVIDER)

    shown = sync._enrich_agent(row, {}, {PRESENTED.key: PRESENTED})

    assert shown.name == "ACME Account Director"
    assert shown.logo_url == "https://api.example.com/modules/acme/assets/public/acme.png"
    assert shown.suggestions == [
        {
            "label": "State of the account",
            "value": "Brief me on ACME.",
            "description": "One screen",
        },
        {"label": "Who leads?", "value": "Who leads the ACME account?"},
    ]
    assert shown.resolved_model_id is None
    assert shown.module_path == "acme.accounts"


def test_an_https_avatar_is_kept_and_anything_else_dropped():
    assert (
        sync._remote_avatar_url("https://cdn.example.com/a.png") == "https://cdn.example.com/a.png"
    )
    assert sync._remote_avatar_url("javascript:alert(1)") is None
    assert sync._remote_avatar_url("") is None


def test_a_remote_row_without_discovery_keeps_its_stored_name():
    row = replace(
        _record("r", PRESENTED.key, provider=REMOTE_PROVIDER), name="ACME Account Director"
    )

    shown = sync._enrich_agent(row, {}, {})

    assert shown.name == "ACME Account Director"
    assert shown.logo_url is None and shown.suggestions is None


def test_presentation_is_read_from_discovery_only_when_stale_and_needed(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote import factory

    calls = []

    class _Directory:
        async def list_agents(self):
            calls.append(1)
            return [PRESENTED]

    monkeypatch.setattr(factory, "get_remote_agent_directory", lambda: _Directory())
    monkeypatch.setattr(sync, "_remote_presentation", None)
    local = [_record("zen", ZEN)]
    remote = [_record("r", PRESENTED.key, provider=REMOTE_PROVIDER)]

    assert asyncio.run(sync._remote_agents_by_key(local)) == {}
    assert calls == []
    assert asyncio.run(sync._remote_agents_by_key(remote)) == {PRESENTED.key: PRESENTED}
    assert asyncio.run(sync._remote_agents_by_key(remote)) == {PRESENTED.key: PRESENTED}
    assert calls == [1]
