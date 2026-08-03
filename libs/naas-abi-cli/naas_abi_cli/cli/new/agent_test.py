"""Tests for the agent scaffold produced by `abi new agent`.

The generated agent ships with the `onHumanMessage` / `onAImessage` message
hooks already wired, as empty stubs the user fills in. These tests pin that
contract: the file must import, the hooks must really override the base class,
and the shipped no-op bodies must be safe to run untouched.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

from naas_abi_cli.cli.new.agent import new_agent


def _generate(tmp_path: Path) -> Any:
    """Run the generator and import the agent class it produced."""
    new_agent("my-test", str(tmp_path))

    generated = tmp_path / "MyTestAgent.py"
    assert generated.exists(), f"generator produced: {list(tmp_path.iterdir())}"

    spec = importlib.util.spec_from_file_location("MyTestAgent", generated)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["MyTestAgent"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("MyTestAgent", None)
    return module.MyTestAgent


RUFF = shutil.which("ruff")


@pytest.mark.skipif(RUFF is None, reason="ruff not on PATH")
@pytest.mark.parametrize(
    "agent_name", ["a", "my-test", "super-long-enterprise-reporting-assistant"]
)
def test_generated_agent_passes_ruff(tmp_path: Path, agent_name: str) -> None:
    """The scaffold must clear the repo's own lint gate, whatever it is named."""
    assert RUFF is not None  # guaranteed by the skipif above
    new_agent(agent_name, str(tmp_path))
    (generated,) = tmp_path.glob("*Agent.py")

    for command in (["format", "--check"], ["check"]):
        result = subprocess.run(
            [RUFF, *command, str(generated)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_generated_agent_defines_both_message_hooks(tmp_path: Path) -> None:
    agent_cls = _generate(tmp_path)

    # Defined on the generated class itself, not merely inherited.
    assert "onHumanMessage" in vars(agent_cls)
    assert "onAImessage" in vars(agent_cls)
    assert agent_cls.onHumanMessage is not Agent.onHumanMessage
    assert agent_cls.onAImessage is not Agent.onAImessage


def test_generated_hooks_ship_as_safe_noops(tmp_path: Path) -> None:
    """The scaffold must run untouched: empty bodies that return nothing."""
    agent_cls = _generate(tmp_path)
    instance = agent_cls.__new__(agent_cls)

    assert instance.onHumanMessage(None) is None
    assert instance.onAImessage(None, "any-agent") is None


def test_generated_agent_hooks_fire_on_a_real_turn(tmp_path: Path) -> None:
    """The hooks are wired by default -- a subclass filling them in gets called."""
    agent_cls = _generate(tmp_path)

    human: list[Any] = []
    ai: list[tuple[Any, str]] = []

    class _Probe(agent_cls):  # type: ignore[misc,valid-type]
        def onHumanMessage(self, message: Any) -> None:
            human.append(message.content)

        def onAImessage(self, message: Any, agent_name: str) -> None:
            ai.append((message.content, agent_name))

    agent = _Probe(
        name="Probe",
        description="probe",
        chat_model=FakeListChatModel(responses=["hello from the model"]),
        tools=[],
        agents=[],
        memory=None,
        state=AgentSharedState(thread_id="0"),
        configuration=AgentConfiguration(system_prompt="you are a probe"),
    )

    assert agent.invoke("ping") == "hello from the model"
    assert human == ["ping"]
    assert ai == [("hello from the model", "Probe")]
