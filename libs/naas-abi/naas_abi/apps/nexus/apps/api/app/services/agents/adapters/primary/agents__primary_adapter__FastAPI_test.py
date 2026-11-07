"""Unit tests for agent sync dedupe helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
    _canonical_agent_sort_key,
    _class_declared_model_ids,
    _nexus_abi_class_name,
    _resolve_workspace_default_class_name,
    pick_workspace_chat_agent_id,
    pick_workspace_documents_agent_id,
    pick_workspace_slides_agent_id,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord


def _agent(
    *,
    agent_id: str,
    is_default: bool = False,
    created_offset_s: int = 0,
    name: str = "Abi",
    class_name: str = "naas_abi.agents.AbiAgent/AbiAgent",
) -> AgentRecord:
    base = datetime(2026, 7, 31, 10, 0, 0)
    return AgentRecord(
        id=agent_id,
        workspace_id="ws-test",
        name=name,
        description="",
        class_name=class_name,
        module_path=class_name.split("/", 1)[0] if "/" in class_name else class_name,
        system_prompt=None,
        model_id=None,
        provider="abi",
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
