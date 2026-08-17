"""Unit tests for agent sync dedupe helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
    _canonical_agent_sort_key,
    _class_declared_model_ids,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord


def _agent(
    *,
    agent_id: str,
    is_default: bool = False,
    enabled: bool = False,
    created_offset_s: int = 0,
) -> AgentRecord:
    base = datetime(2026, 7, 31, 10, 0, 0)
    return AgentRecord(
        id=agent_id,
        workspace_id="ws-test",
        name="Abi",
        description="",
        enabled=enabled,
        class_name="naas_abi.agents.AbiAgent/AbiAgent",
        module_path="naas_abi.agents.AbiAgent",
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
