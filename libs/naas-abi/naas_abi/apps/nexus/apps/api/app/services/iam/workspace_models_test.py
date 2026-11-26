"""The chat models a workspace uses (``workspace_models``): its offer's Models section,
the default model an agent switches to, and the substitute the engine asks for a
remote module's turn. Pure, but for the hook's reader, which a test passes."""

from __future__ import annotations

import asyncio
import threading

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import workspace_models
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_models import (
    UNRESTRICTED,
    ModelNotOfferedError,
    WorkspaceModels,
    models_of,
    validated,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

ONLY_QWEN = WorkspaceModels(frozenset({"qwen-3.8"}), "qwen-3.8")


def test_an_offer_with_no_models_section_or_every_model_is_unrestricted():
    assert models_of(None) == UNRESTRICTED
    assert models_of(Offer()) == UNRESTRICTED
    every = models_of(Offer.of(models=["*"], default_model="gpt-x"))
    assert not every.restricted and every.default == "gpt-x"
    assert every.model_for("anything") == "anything"
    assert every.allows("anything")


def test_a_restricted_workspace_keeps_its_models_and_switches_the_others():
    models = models_of(Offer.of(models=["qwen-3.8", "gpt-x"], default_model="qwen-3.8"))
    assert models.restricted
    assert models.model_for("gpt-x") == "gpt-x"
    assert models.model_for("claude-y") == "qwen-3.8"
    assert models.model_for(None) == "qwen-3.8"
    assert models.narrowed(["claude-y", "gpt-x", "qwen-3.8"]) == ["gpt-x", "qwen-3.8"]


def test_a_restricted_workspace_with_no_default_refuses():
    models = WorkspaceModels(frozenset({"qwen-3.8"}), None)
    with pytest.raises(ModelNotOfferedError) as refused:
        models.model_for("gpt-x")
    assert isinstance(refused.value, PermissionDeniedError)
    assert "gpt-x" in str(refused.value)
    models.require("qwen-3.8")
    with pytest.raises(ModelNotOfferedError):
        ONLY_QWEN.require("gpt-x")


def test_what_a_setting_may_say():
    assert validated(["*"], None) == (frozenset({"*"}), None)
    assert validated(["*", "gpt-x"], "gpt-x") == (frozenset({"*"}), "gpt-x")
    assert validated(["qwen-3.8"], "qwen-3.8") == (frozenset({"qwen-3.8"}), "qwen-3.8")
    for models, default in ((["qwen-3.8"], None), (["qwen-3.8"], "gpt-x"), ([], None)):
        with pytest.raises(ValueError):
            validated(models, default)


def test_the_engine_substitute_reads_the_container_and_keeps_out_of_no_container():
    seen: list[str] = []

    def read(container: str) -> WorkspaceModels:
        seen.append(container)
        return ONLY_QWEN if container == "ws-a" else UNRESTRICTED

    substitute = workspace_models.substitute_with(read)
    assert substitute("ws-a", "gpt-x") == "qwen-3.8"
    assert substitute("ws-a", "qwen-3.8") == "qwen-3.8"
    assert substitute("ws-b", "gpt-x") == "gpt-x"
    assert substitute(None, "gpt-x") == "gpt-x"
    assert seen == ["ws-a", "ws-a", "ws-b"]


def test_the_blocking_reader_runs_on_the_loop_it_was_given():
    """The engine asks from a worker thread; the offer is read on Nexus's loop."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:

        async def read(container: str) -> WorkspaceModels:
            return ONLY_QWEN

        blocking = workspace_models.blocking_reader(read, loop)
        assert blocking("ws-a") == ONLY_QWEN
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
        loop.close()


@pytest.mark.asyncio
async def test_a_turns_models_are_those_it_was_given_else_its_containers(monkeypatch):
    async def read(container: str) -> WorkspaceModels:
        return ONLY_QWEN if container == "ws-a" else UNRESTRICTED

    monkeypatch.setattr(workspace_models, "models_in_container", read)
    assert await workspace_models.models_for_turn() == UNRESTRICTED
    with workspace_models.for_turn(ONLY_QWEN):
        assert await workspace_models.models_for_turn() == ONLY_QWEN
    from dataclasses import replace

    from naas_abi_core.engine.call_context import current_call_context, use_call_context

    with use_call_context(replace(current_call_context(), container="ws-a")):
        assert await workspace_models.models_for_turn() == ONLY_QWEN


def test_the_model_a_turn_runs_on_by_provider():
    """In-process agents switch (picked: that model; none picked: the default when the
    agent's own is not offered); a remote module is the engine's to switch; an ABI
    server's agent or a provider of its own cannot switch: refused when not offered."""
    turn = workspace_models.turn_llm_model
    inprocess = {"provider_type": "abi", "endpoint": "inprocess://abi", "provider_model": "A"}
    assert turn(UNRESTRICTED, llm_model="gpt-x", **inprocess) == "gpt-x"
    assert turn(ONLY_QWEN, llm_model="gpt-x", **inprocess) == "qwen-3.8"
    assert turn(ONLY_QWEN, llm_model=None, agent_models=lambda: {"gpt-x"}, **inprocess) == (
        "qwen-3.8"
    )
    assert turn(ONLY_QWEN, llm_model=None, agent_models=lambda: set(), **inprocess) == "qwen-3.8"
    assert turn(ONLY_QWEN, llm_model=None, agent_models=lambda: {"qwen-3.8"}, **inprocess) is None
    remote = {"provider_type": "remote", "endpoint": None, "provider_model": "mod/Agent"}
    assert turn(ONLY_QWEN, llm_model=None, **remote) is None
    with pytest.raises(ModelNotOfferedError):
        turn(
            ONLY_QWEN,
            llm_model=None,
            provider_type="abi",
            endpoint="https://abi.example",
            provider_model="Agent",
        )
    own = {"provider_type": "openai", "endpoint": None}
    assert turn(ONLY_QWEN, llm_model=None, provider_model="qwen-3.8", **own) is None
    with pytest.raises(ModelNotOfferedError):
        turn(ONLY_QWEN, llm_model=None, provider_model="gpt-x", **own)
    assert turn(UNRESTRICTED, llm_model=None, provider_model="gpt-x", **own) is None
