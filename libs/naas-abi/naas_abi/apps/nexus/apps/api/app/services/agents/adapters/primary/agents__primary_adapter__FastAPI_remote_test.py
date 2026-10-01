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

    async def list_workspace_agents(self, context, workspace_id):
        return list(self.records.values())

    async def create_agent(self, context, data):
        now = datetime(2026, 10, 1)
        record = AgentRecord(
            id=f"a-{len(self.records) + 1}",
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description or "",
            enabled=data.enabled,
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

    async def update_agent(self, context, agent_id, updates):
        known = {f.name for f in fields(AgentRecord)}
        changes = {
            f.name: getattr(updates, f.name)
            for f in fields(updates)
            if getattr(updates, f.name) is not None and f.name in known
        }
        self.records[agent_id] = replace(self.records[agent_id], **changes)
        return self.records[agent_id]

    async def delete_agent(self, context, agent_id):
        self.deleted.append(agent_id)
        return self.records.pop(agent_id, None) is not None


def _record(
    agent_id: str,
    class_name: str,
    *,
    provider: str = "abi",
    enabled: bool = True,
    default: bool = False,
):
    now = datetime(2026, 10, 1)
    return AgentRecord(
        id=agent_id,
        workspace_id="ws",
        name=class_name.rsplit("/", 1)[-1],
        description="",
        enabled=enabled,
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


@pytest.fixture
def seed(monkeypatch):
    """Set the workspace seed: None (no config entry) or an ``agents:`` list."""
    state = {"seed": None}

    async def slug(workspace_id):
        return "ws"

    monkeypatch.setattr(sync, "_workspace_slug", slug)
    monkeypatch.setattr(sync, "workspace_seed_for_slug", lambda s: state["seed"])
    monkeypatch.setattr(sync, "_get_engine_default_agent_class_name", lambda: ZEN)
    monkeypatch.setattr(sync, "request_context", lambda user: None)

    def set_seed(agents):
        state["seed"] = SimpleNamespace(agents=agents, default_agent=None)

    return set_seed


def _sync(agents: _Agents, remote_agents):
    return asyncio.run(
        sync._reconcile_workspace_agents(
            agents,
            SimpleNamespace(id="u-1"),
            "ws",
            list(agents.records.values()),
            {ZEN: _ZenAgent},
            remote_agents=remote_agents,
        )
    )


def _by_class(records):
    return {r.class_name: r for r in records}


def test_without_a_roster_discovered_agents_are_created_and_enabled(seed):
    agents = _Agents([_record("zen", ZEN, default=True)])

    result = _by_class(_sync(agents, [RESEARCHER]))

    researcher = result[RESEARCHER.key]
    assert (researcher.provider, researcher.enabled) == (REMOTE_PROVIDER, True)
    assert (researcher.name, researcher.description) == (
        "Researcher",
        "Answers research questions.",
    )
    assert researcher.module_path == "acme.research"
    assert result[ZEN].enabled and result[ZEN].is_default


def test_a_roster_restricts_discovered_agents_to_those_it_lists(seed):
    seed(["zen ZenAgent", "acme.research Researcher"])
    agents = _Agents([_record("zen", ZEN, default=True)])

    result = _by_class(_sync(agents, [RESEARCHER, WRITER]))

    assert result[RESEARCHER.key].enabled
    assert not result[WRITER.key].enabled


def test_an_unavailable_remote_agent_is_disabled_not_deleted(seed):
    agents = _Agents(
        [_record("zen", ZEN, default=True), _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER)]
    )

    result = _by_class(_sync(agents, []))

    assert agents.deleted == []
    assert result[RESEARCHER.key].enabled is False


def test_it_is_enabled_again_when_its_module_returns(seed):
    agents = _Agents(
        [
            _record("zen", ZEN, default=True),
            _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER, enabled=False),
        ]
    )

    assert _by_class(_sync(agents, [RESEARCHER]))[RESEARCHER.key].enabled


def test_unknown_discovery_state_leaves_remote_rows_alone(seed):
    agents = _Agents(
        [_record("zen", ZEN, default=True), _record("r", RESEARCHER.key, provider=REMOTE_PROVIDER)]
    )

    result = _by_class(_sync(agents, None))

    assert result[RESEARCHER.key].enabled
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
