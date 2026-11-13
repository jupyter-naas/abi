"""The Bodo agent runs no code of its own: scripts run in the caller's coding
workspace, through the default workspace tools."""

from __future__ import annotations

from types import SimpleNamespace

import naas_abi_marketplace.applications.bodo as bodo_pkg
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from naas_abi_marketplace.applications.bodo.agents.BodoAgent import BodoAgent


@pytest.fixture
def bodo_module(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = FakeMessagesListChatModel(responses=[AIMessage(content="ok")])
    module = SimpleNamespace(
        engine=SimpleNamespace(
            services=SimpleNamespace(
                model_registry=SimpleNamespace(get_default_chat_model=lambda: chat)
            )
        )
    )
    monkeypatch.setattr(
        bodo_pkg.ABIModule, "get_instance", classmethod(lambda cls: module)
    )


def test_bodo_agent_keeps_code_off_the_engine_host(bodo_module: None) -> None:
    from naas_abi_core.services.agent.tools.workspace_tools import (
        workspace_tools,
    )

    agent = BodoAgent.New()
    names = {tool.name for tool in agent.tools if hasattr(tool, "name")}

    assert "execute_python_code" not in names
    # Every tool that runs or writes anything is a workspace tool, bound to the
    # caller's own coding workspace.
    workspace = {tool.name for tool in workspace_tools()}
    assert names - workspace <= {"get_time_date"}
    for tool in agent.tools:
        func = getattr(tool, "func", None)
        assert "__demo__" not in getattr(func, "__module__", ""), tool
