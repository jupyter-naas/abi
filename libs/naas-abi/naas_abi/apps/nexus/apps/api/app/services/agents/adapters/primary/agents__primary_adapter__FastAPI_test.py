"""Unit tests for agent sync dedupe helpers."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
    _canonical_agent_sort_key,
    _class_declared_model_ids,
    _nexus_abi_class_name,
    _resolve_workspace_default_class_name,
    mark_fronted_agents,
    pick_workspace_chat_agent_id,
    pick_workspace_documents_agent_id,
    pick_workspace_slides_agent_id,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import REMOTE_PROVIDER
from naas_abi_core.services.agent.Agent import Agent


def _agent(
    *,
    agent_id: str,
    is_default: bool = False,
    created_offset_s: int = 0,
    name: str = "Abi",
    class_name: str | None = "naas_abi.agents.AbiAgent/AbiAgent",
    provider: str = "abi",
) -> AgentRecord:
    base = datetime(2026, 7, 31, 10, 0, 0)
    return AgentRecord(
        id=agent_id,
        workspace_id="ws-test",
        name=name,
        description="",
        class_name=class_name,
        module_path=class_name.split("/", 1)[0] if class_name and "/" in class_name else class_name,
        system_prompt=None,
        model_id=None,
        provider=provider,
        logo_url=None,
        created_at=base + timedelta(seconds=created_offset_s),
        updated_at=base + timedelta(seconds=created_offset_s),
        is_default=is_default,
    )


def test_canonical_agent_sort_prefers_default_then_oldest() -> None:
    newest = _agent(agent_id="d", created_offset_s=30)
    middle = _agent(agent_id="e", created_offset_s=20)
    default = _agent(agent_id="a", is_default=True, created_offset_s=10)
    oldest = _agent(agent_id="b", created_offset_s=5)

    ordered = sorted([newest, middle, default, oldest], key=_canonical_agent_sort_key)
    assert [agent.id for agent in ordered] == ["a", "b", "e", "d"]


def test_class_declared_model_ids_reads_getter_then_attr_then_single() -> None:
    class Multi:
        @classmethod
        def get_chat_model_ids(cls) -> list[str]:
            return ["gpt-5.2", "gpt-5.6-sol"]

    class AttrOnly:
        MODEL_IDS = ("a", "b")

    class Single:
        @classmethod
        def get_chat_model_id(cls) -> str:
            return "claude-sonnet-5"

    assert _class_declared_model_ids(Multi) == ["gpt-5.2", "gpt-5.6-sol"]
    assert _class_declared_model_ids(AttrOnly) == ["a", "b"]
    assert _class_declared_model_ids(Single) == ["claude-sonnet-5"]
    assert _class_declared_model_ids(object) == []


def test_resolve_workspace_default_falls_back_to_abi() -> None:
    registry = {"naas_abi.agents.AbiAgent/AbiAgent": object()}
    assert _resolve_workspace_default_class_name(registry) == "naas_abi.agents.AbiAgent/AbiAgent"


def test_nexus_abi_class_name_only_matches_our_orchestrator() -> None:
    """Abi is the default's fallback, so the match must not be loose: an
    ``AbiAgent`` from another module is not the platform orchestrator."""
    assert (
        _nexus_abi_class_name(
            [
                "naas_abi.agents.AppsAgent/AppsAgent",
                "naas_abi.agents.AbiAgent/AbiAgent",
            ]
        )
        == "naas_abi.agents.AbiAgent/AbiAgent"
    )
    assert _nexus_abi_class_name(["acme.agents.AbiAgent/AbiAgent"]) is None
    assert _nexus_abi_class_name(["naas_abi.agents.AbiAgentHelper/AbiAgentHelper"]) is None
    assert _nexus_abi_class_name([]) is None


def test_pick_workspace_chat_agent_rejects_ids_the_caller_may_not_use() -> None:
    """``agents`` are those the caller may use: an id outside them (another
    workspace's, one IAM refuses) falls back to the default."""
    default = _agent(agent_id="default", is_default=True)
    local = _agent(agent_id="local")
    agents = [default, local]

    assert pick_workspace_chat_agent_id(agents, "local") == "local"
    assert pick_workspace_chat_agent_id(agents, "stale-from-other-ws") == "default"
    assert pick_workspace_chat_agent_id(agents, None) == "default"
    assert pick_workspace_chat_agent_id([], "local") is None


def test_pick_workspace_chat_agent_falls_back_to_abi_without_default() -> None:
    maps = _agent(
        agent_id="maps",
        name="Maps",
        class_name="naas_abi.agents.MapsAgent/MapsAgent",
    )
    abi = _agent(agent_id="abi")
    lookalike = _agent(
        agent_id="acme",
        name="Acme",
        class_name="acme.agents.AbiAgent/AbiAgent",
    )
    default = _agent(
        agent_id="default",
        is_default=True,
        name="Bob",
        class_name="bob.agents.BobAgent/BobAgent",
    )

    assert pick_workspace_chat_agent_id([maps, abi], None) == "abi"
    assert pick_workspace_chat_agent_id([maps, lookalike], None) == "maps"
    assert pick_workspace_chat_agent_id([lookalike, maps], None) == "acme"
    assert pick_workspace_chat_agent_id([maps, abi, default], None) == "default"


def test_pick_workspace_slides_agent_is_the_office_slides_the_caller_may_use() -> None:
    default = _agent(agent_id="default", is_default=True, name="Orchestrator")
    slides = _agent(
        agent_id="slides",
        name="Slides",
        class_name="naas_abi.agents.SlidesAgent/SlidesAgent",
    )
    other = _agent(
        agent_id="sheet",
        name="Office Slides",
        class_name="acme.office.agents.SheetSlidesAgent/SheetSlidesAgent",
    )
    assert pick_workspace_slides_agent_id([default, other, slides]) == "slides"
    assert pick_workspace_slides_agent_id([default, other]) is None


def test_pick_workspace_documents_agent_is_the_office_documents_the_caller_may_use() -> None:
    default = _agent(agent_id="default", is_default=True, name="Orchestrator")
    documents = _agent(
        agent_id="documents",
        name="Documents",
        class_name="naas_abi.agents.DocumentsAgent/DocumentsAgent",
    )
    other = _agent(
        agent_id="sheet",
        name="Office Documents",
        class_name="acme.office.agents.SheetDocumentsAgent/SheetDocumentsAgent",
    )
    assert pick_workspace_documents_agent_id([default, other, documents]) == "documents"
    assert pick_workspace_documents_agent_id([default, other]) is None


class _JoeAgent(AbiAgent):
    fronts_its_agents = True


class _PlainAbiAgent(AbiAgent):
    pass


class _AppsAgent(Agent):
    pass


class _BobAgent(Agent):
    delegates_to_abi = True


ABI = "naas_abi.agents.AbiAgent/AbiAgent"
JOE = "joe.agents.JoeAgent/JoeAgent"
PLAIN = "acme.agents.PlainAbiAgent/PlainAbiAgent"
APPS = "naas_abi.agents.AppsAgent/AppsAgent"
BOB = "bob.agents.BobAgent/BobAgent"
CLASSES = {
    ABI: AbiAgent,
    JOE: _JoeAgent,
    PLAIN: _PlainAbiAgent,
    APPS: _AppsAgent,
    BOB: _BobAgent,
}


def _roster(default_class: str | None) -> list[AgentRecord]:
    rows = [
        _agent(agent_id="abi", class_name=ABI),
        _agent(agent_id="joe", name="Joe", class_name=JOE),
        _agent(agent_id="plain", name="Plain", class_name=PLAIN),
        _agent(agent_id="apps", name="Apps", class_name=APPS),
        _agent(agent_id="bob", name="Bob", class_name=BOB),
        _agent(
            agent_id="remote", name="Remote", class_name="acme/Remote", provider=REMOTE_PROVIDER
        ),
        _agent(agent_id="built", name="Built", class_name=None, provider="openai"),
    ]
    return [
        replace(row, is_default=row.class_name == default_class) if default_class else row
        for row in rows
    ]


def _in_picker(agents: list[AgentRecord]) -> list[str]:
    return [agent.id for agent in agents if agent.in_chat_picker]


def test_a_fronting_default_leaves_abi_and_its_sub_agents_out_of_the_pickers() -> None:
    marked = mark_fronted_agents(_roster(JOE), CLASSES)

    # Every row stays listed: a section's pane still binds its office agent.
    assert [agent.id for agent in marked] == [agent.id for agent in _roster(JOE)]
    # Abi and Apps are reached through Joe. Another orchestrator, a supervisor
    # over Abi, a remote agent and one the workspace built are not.
    assert _in_picker(marked) == ["joe", "plain", "bob", "remote", "built"]


def test_the_pickers_offer_everything_unless_the_default_fronts() -> None:
    every = ["abi", "joe", "plain", "apps", "bob", "remote", "built"]
    for default in (ABI, PLAIN, APPS, None):
        assert _in_picker(mark_fronted_agents(_roster(default), CLASSES)) == every


def test_a_fronting_default_missing_from_the_registry_fronts_nothing() -> None:
    marked = mark_fronted_agents(_roster(JOE), {k: v for k, v in CLASSES.items() if k != JOE})
    assert all(agent.in_chat_picker for agent in marked)
