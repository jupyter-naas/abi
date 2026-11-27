"""An agent's own model is always allowed: a Member chats with a module agent whose
model is outside their model set, while a direct chat with that model is refused.
The registry's gate and IAM are real; the agent is a minimal stand-in of a module
agent class (its chat model and its sub-agents)."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import class_scope
from naas_abi.apps.nexus.apps.api.app.services.iam import model_sets
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    _inprocess_agent_class_name,
    agent_model_owners,
    agents_own_models,
)
from naas_abi_core.engine.call_context import as_service_account, inside, use_call_context
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.iam.tests.authorization_contract import wire
from naas_abi_core.services.model_registry.ModelRegistryPort import ModelNotFoundError
from naas_abi_core.services.model_registry.ModelRegistryService import ModelRegistryService

W = workspace_container("acme", "w")


class AnalystAgent:
    """A module agent: built at boot with its own model, declaring the models a turn
    may switch it to."""

    def __init__(self, chat_model, agents=()):
        self._chat_model = chat_model
        self._agents = list(agents)

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return ["large", "larger"]


class HelperAgent(AnalystAgent):
    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return []


def _registry(iam) -> ModelRegistryService:
    registry = ModelRegistryService()
    for canonical_id in ("small", "large", "larger", "helper-model"):
        registry.register(
            canonical_id,
            ChatModel(
                model_id=canonical_id,
                provider="demo",
                model=FakeListChatModel(responses=["answer"] * 50),
            ),
        )
    return wire(registry, iam)


@pytest.fixture
def world():
    model_sets.forget()
    nexus = NexusIam(features_with_roles=False)
    nexus.workspace("acme", "w")
    nexus.grant("member", "member", W)
    registry = _registry(nexus.iam)
    with as_service_account("engine"):
        large = registry.get_chat_model("large").model
        helper_model = registry.get_chat_model("helper-model").model
    with as_service_account("api"):
        policies = model_sets.ensure_model_policies(nexus.iam, ["small"], [])
        for policy_id in (policies.member,):
            nexus.iam.attach_policy(policy_id, nexus.principal("member"), None)
    analyst_scope = class_scope(_inprocess_agent_class_name(AnalystAgent(None)), AnalystAgent)
    nexus.allow_scope("member", analyst_scope, W)
    agent = AnalystAgent(large, agents=[HelperAgent(helper_model)])
    with nexus.installed():
        yield nexus, registry, agent, large, helper_model
    model_sets.forget()


def _as_member_in_w():
    return use_call_context(NexusIam.context("member"))


def test_a_member_chats_with_an_agent_whose_model_is_outside_their_set(world):
    _nexus, registry, agent, large, _helper = world
    with _as_member_in_w(), inside(W):
        with agents_own_models(agent):
            assert large.invoke("hi").content == "answer"
            # Switched to another model the agent declares: its own too.
            assert registry.get_chat_model("larger") is not None


def test_a_direct_model_chat_outside_the_set_is_refused(world):
    _nexus, registry, _agent, large, _helper = world
    with _as_member_in_w(), inside(W):
        assert registry.get_chat_model("small") is not None
        with pytest.raises(ModelNotFoundError):
            large.invoke("hi")
        with pytest.raises(ModelNotFoundError):
            registry.get_chat_model("large")


def test_a_sub_agent_the_member_may_not_use_lends_its_model_to_nobody(world):
    _nexus, registry, agent, _large, helper_model = world
    with _as_member_in_w(), inside(W):
        owners = agent_model_owners(agent, W)
        assert set(owners) == {"large", "larger", "helper-model"}
        with agents_own_models(agent), pytest.raises(ModelNotFoundError):
            helper_model.invoke("hi")
        # A model no agent of the turn owns stays the member's set's.
        with agents_own_models(agent), pytest.raises(ModelNotFoundError):
            registry.get_chat_model("small-unknown")


def test_a_turn_in_no_workspace_lends_nothing(world):
    _nexus, _registry, agent, large, _helper = world
    assert agent_model_owners(agent, None) == {}
    with _as_member_in_w(), agents_own_models(agent), pytest.raises(ModelNotFoundError):
        large.invoke("hi")


# -- a workspace limited to some models (``iam/workspace_models``) ---------------------------


def test_a_limited_workspace_lends_only_the_models_it_offers(world):
    """The loan of an agent's own models is narrowed to what the workspace uses: a
    model it does not offer is the member's set's again (refused here)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_models import WorkspaceModels

    _nexus, _registry, agent, large, _helper = world
    only_larger = WorkspaceModels(frozenset({"larger"}), "larger")
    with _as_member_in_w(), inside(W):
        with agents_own_models(agent, only_larger), pytest.raises(ModelNotFoundError):
            large.invoke("hi")
        with agents_own_models(agent, WorkspaceModels()):
            assert large.invoke("hi").content == "answer"


def test_each_agent_of_a_turn_on_a_model_not_offered_switches_to_the_default(world):
    """The turn's agent and each of its sub-agents: one on a model the workspace does
    not offer (or on one the registry cannot name) is switched to its default; one on an
    offered model keeps it."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_models import WorkspaceModels
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
        keep_agent_to_models,
    )

    _nexus, registry, agent, large, helper_model = world
    with as_service_account("engine"):
        larger = registry.get_chat_model("larger").model
    loaded: list[str] = []

    def load(model_id: str):
        loaded.append(model_id)
        return larger

    switched = keep_agent_to_models(
        agent, WorkspaceModels(frozenset({"large", "larger"}), "larger"), load=load
    )
    assert agent._chat_model is large  # offered: kept
    assert agent._agents[0]._chat_model is larger  # helper-model is not: switched
    assert switched == ["HelperAgent"] and loaded == ["larger"]
    unknown = HelperAgent(FakeListChatModel(responses=["x"]))
    keep_agent_to_models(unknown, WorkspaceModels(frozenset({"larger"}), "larger"), load=load)
    assert unknown._chat_model is larger
    # Every model: nothing switched.
    assert keep_agent_to_models(AnalystAgent(helper_model), WorkspaceModels(), load=load) == []


@pytest.mark.asyncio
async def test_a_turns_model_is_kept_to_its_workspaces(world, monkeypatch):
    """A picked model the workspace does not offer runs on its default; none picked,
    the agents are switched node by node; no default: refused."""
    from naas_abi.apps.nexus.apps.api.app.services import provider_runtime
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_models import (
        ModelNotOfferedError,
        WorkspaceModels,
        for_turn,
    )

    _nexus, _registry, agent, _large, _helper = world
    seen: list[str] = []
    monkeypatch.setattr(
        provider_runtime,
        "keep_agent_to_models",
        lambda node, models: seen.append(type(node).__name__) or [],
    )
    limited = WorkspaceModels(frozenset({"larger"}), "larger")
    with for_turn(limited):
        assert await provider_runtime._workspace_models_for_turn(agent, "large") == (
            limited,
            "larger",
        )
        assert await provider_runtime._workspace_models_for_turn(agent, "larger") == (
            limited,
            "larger",
        )
        assert await provider_runtime._workspace_models_for_turn(agent, None) == (limited, None)
    assert seen == ["AnalystAgent"]
    with (
        for_turn(WorkspaceModels(frozenset({"larger"}), None)),
        pytest.raises(ModelNotOfferedError),
    ):
        await provider_runtime._workspace_models_for_turn(agent, "large")
    with for_turn(WorkspaceModels()):
        assert (await provider_runtime._workspace_models_for_turn(agent, "large"))[1] == "large"
