"""Unit tests for agent sync dedupe helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
    _canonical_agent_sort_key,
    _class_declared_model_ids,
    _nexus_abi_class_name,
    _roster_alignment,
    _workspace_agent_roster,
    pick_workspace_chat_agent_id,
    pick_workspace_documents_agent_id,
    pick_workspace_slides_agent_id,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord


def _agent(
    *,
    agent_id: str,
    is_default: bool = False,
    enabled: bool = False,
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
        enabled=enabled,
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


def test_canonical_agent_sort_prefers_default_then_enabled_then_oldest() -> None:
    disabled_new = _agent(agent_id="d", enabled=False, created_offset_s=30)
    enabled_mid = _agent(agent_id="e", enabled=True, created_offset_s=20)
    default_old = _agent(agent_id="a", is_default=True, enabled=True, created_offset_s=10)
    enabled_old = _agent(agent_id="b", enabled=True, created_offset_s=5)

    ordered = sorted(
        [disabled_new, enabled_mid, default_old, enabled_old],
        key=_canonical_agent_sort_key,
    )
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


def test_workspace_agent_roster_uses_seed_when_present() -> None:
    assert _workspace_agent_roster({"mod/Listed"}, "mod/Default") == {"mod/Listed"}
    assert _workspace_agent_roster(set(), "mod/Default") == set()


def test_workspace_agent_roster_unseeded_is_default_only() -> None:
    assert _workspace_agent_roster(None, "mod/Default") == {"mod/Default"}


def test_nexus_abi_class_name_only_matches_our_orchestrator() -> None:
    """Abi is force-enabled on every roster, so the match must not be loose.

    An ``AbiAgent`` from another module would otherwise be switched on in a
    workspace that never listed it.
    """
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


ABI = "naas_abi.agents.AbiAgent/AbiAgent"
REGISTRY = ["axi.agents.AxiAgent/AxiAgent", "naas_abi.agents.AppsAgent/AppsAgent", ABI]


def test_roster_alignment_always_enables_the_orchestrator() -> None:
    """Abi rides on every roster, whatever the workspace listed."""
    roster, align = _roster_alignment({"axi.agents.AxiAgent/AxiAgent"}, None, REGISTRY)
    assert roster == {"axi.agents.AxiAgent/AxiAgent", ABI}
    assert align is True

    roster, align = _roster_alignment(None, "axi.agents.AxiAgent/AxiAgent", REGISTRY)
    assert roster == {"axi.agents.AxiAgent/AxiAgent", ABI}
    assert align is True


def test_roster_alignment_keeps_the_empty_roster_guard() -> None:
    """No seed and no resolvable default still means "touch nothing".

    Abi is added after the decision, so it must not turn this case into
    "roster = {Abi}" and disable every other row.
    """
    roster, align = _roster_alignment(None, None, REGISTRY)
    assert roster == {ABI}
    assert align is False


def test_roster_alignment_still_empties_an_explicitly_empty_seed() -> None:
    """``agents: []`` disables everything but the orchestrator."""
    roster, align = _roster_alignment(set(), None, REGISTRY)
    assert roster == {ABI}
    assert align is True


def test_roster_alignment_without_abi_in_the_registry() -> None:
    roster, align = _roster_alignment(
        {"axi.agents.AxiAgent/AxiAgent"}, None, ["axi.agents.AxiAgent/AxiAgent"]
    )
    assert roster == {"axi.agents.AxiAgent/AxiAgent"}
    assert align is True


def test_pick_workspace_chat_agent_rejects_foreign_and_disabled_ids() -> None:
    default = _agent(agent_id="default", is_default=True, enabled=False)
    local = _agent(agent_id="local", enabled=True)
    agents = [default, local]

    assert pick_workspace_chat_agent_id(agents, "local") == "local"
    assert pick_workspace_chat_agent_id(agents, "stale-from-other-ws") == "default"
    assert pick_workspace_chat_agent_id(agents, None) == "default"
    assert _workspace_agent_roster(None, None) == set()


def test_pick_workspace_chat_agent_falls_back_to_abi_without_default() -> None:
    maps = _agent(
        agent_id="maps",
        enabled=True,
        name="Maps",
        class_name="naas_abi.agents.MapsAgent/MapsAgent",
    )
    abi = _agent(agent_id="abi", enabled=True)
    lookalike = _agent(
        agent_id="acme",
        enabled=True,
        name="Acme",
        class_name="acme.agents.AbiAgent/AbiAgent",
    )
    default = _agent(
        agent_id="default",
        is_default=True,
        enabled=True,
        name="Bob",
        class_name="bob.agents.BobAgent/BobAgent",
    )

    assert pick_workspace_chat_agent_id([maps, abi], None) == "abi"
    assert pick_workspace_chat_agent_id([maps, lookalike], None) == "maps"
    assert pick_workspace_chat_agent_id([maps, _agent(agent_id="off")], None) == "maps"
    assert pick_workspace_chat_agent_id([maps, abi, default], None) == "default"


def test_pick_workspace_slides_agent_prefers_enabled_office_slides() -> None:
    default = _agent(agent_id="default", is_default=True, enabled=True, name="Orchestrator")
    slides = _agent(
        agent_id="slides",
        enabled=True,
        name="Slides",
        class_name="naas_abi.agents.SlidesAgent/SlidesAgent",
    )
    other = _agent(
        agent_id="sheet",
        enabled=True,
        name="Office Slides",
        class_name="acme.office.agents.SheetSlidesAgent/SheetSlidesAgent",
    )
    disabled = _agent(
        agent_id="off",
        enabled=False,
        name="Slides",
        class_name="naas_abi.agents.SlidesAgent/SlidesAgent",
    )

    assert pick_workspace_slides_agent_id([default, other, slides]) == "slides"
    assert pick_workspace_slides_agent_id([default, other, disabled]) is None
    assert pick_workspace_slides_agent_id([default, other]) is None


def test_pick_workspace_documents_agent_prefers_enabled_office_documents() -> None:
    default = _agent(agent_id="default", is_default=True, enabled=True, name="Orchestrator")
    documents = _agent(
        agent_id="documents",
        enabled=True,
        name="Documents",
        class_name="naas_abi.agents.DocumentsAgent/DocumentsAgent",
    )
    other = _agent(
        agent_id="sheet",
        enabled=True,
        name="Office Documents",
        class_name="acme.office.agents.SheetDocumentsAgent/SheetDocumentsAgent",
    )
    disabled = _agent(
        agent_id="off",
        enabled=False,
        name="Documents",
        class_name="naas_abi.agents.DocumentsAgent/DocumentsAgent",
    )

    assert pick_workspace_documents_agent_id([default, other, documents]) == "documents"
    assert pick_workspace_documents_agent_id([default, other, disabled]) is None
    assert pick_workspace_documents_agent_id([default, other]) is None
