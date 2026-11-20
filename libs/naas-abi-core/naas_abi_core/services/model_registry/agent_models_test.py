"""An agent's own model is decided by the agent's scope, never by the caller's
model set: inside ``agent_models``, a model the agent owns is allowed to whoever
may use the agent; any other model is still the caller's model set's."""

from __future__ import annotations

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.services.iam.module_scopes import scope_resource
from naas_abi_core.services.iam.tests.authorization_contract import contract_iam, wire
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from naas_abi_core.services.model_registry.agent_models import (
    agent_models,
    gated_model_ids,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import ModelNotFoundError
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)

IN_SET = "abi:model_registry:model/small"
AGENT = scope_resource("agent", "acme", "Analyst")
OTHER_AGENT = scope_resource("agent", "acme", "Writer")


def _registry() -> ModelRegistryService:
    registry = ModelRegistryService()
    for canonical_id in ("small", "large"):
        registry.register(
            canonical_id,
            ChatModel(
                model_id=canonical_id,
                provider="demo",
                model=FakeListChatModel(responses=["answer"] * 20),
            ),
        )
    registry.register(
        "embedding",
        EmbeddingModel(
            model_id="embedding",
            provider="demo",
            model=DeterministicFakeEmbedding(size=4),
        ),
    )
    return registry


@pytest.fixture
def world():
    iam = contract_iam()
    h = IAMHarness(iam)
    registry = wire(_registry(), iam)
    with as_service_account("engine"):
        # Agents are built once, at boot, as the engine.
        large = registry.get_chat_model("large").model
        small = registry.get_chat_model("small").model
    bob = h.user("bob")
    # Bob's model set is "small"; he may use the Analyst agent, not the Writer.
    h.grant(
        bob.id,
        statement(
            "Allow",
            [
                "model_registry:ListModels",
                "model_registry:Resolve",
                "model_registry:Chat",
            ],
            [IN_SET],
        ),
        statement("Allow", ["module:UseAgent"], [AGENT]),
    )
    return h, registry, bob, large, small


def test_a_member_chats_with_an_agent_whose_model_is_outside_their_set(world):
    h, registry, bob, large, _small = world
    lent = agent_models("module:UseAgent", {"large": [AGENT]})
    with h.as_(actor="api", on_behalf_of=bob), lent:
        assert large.invoke("hi").content == "answer"
        # Resolving the agent's model for the turn (a model chosen among its own).
        assert registry.get_chat_model("large").model is large


def test_a_direct_model_chat_outside_the_set_is_refused(world):
    h, registry, bob, large, small = world
    with h.as_(actor="api", on_behalf_of=bob):
        assert small.invoke("hi").content == "answer"
        with pytest.raises(ModelNotFoundError):
            large.invoke("hi")
        with pytest.raises(ModelNotFoundError):
            registry.get_chat_model("large")


def test_the_agent_scope_decides_and_other_models_stay_the_callers(world):
    h, _registry, bob, large, _small = world
    refused = pytest.raises(ModelNotFoundError)
    with h.as_(actor="api", on_behalf_of=bob):
        # An agent Bob may not use lends him nothing.
        with agent_models("module:UseAgent", {"large": [OTHER_AGENT]}), refused:
            large.invoke("hi")
        # A model the agent does not own is still Bob's model set's.
        with agent_models("module:UseAgent", {"small": [AGENT]}), refused:
            large.invoke("hi")
    # Outside the block, nothing is lent.
    with h.as_(actor="api", on_behalf_of=bob), pytest.raises(ModelNotFoundError):
        large.invoke("hi")


def test_embeddings_are_not_an_agents(world):
    h, registry, bob, _large, _small = world
    lent = agent_models("module:UseAgent", {"embedding": [AGENT]})
    with h.as_(actor="api", on_behalf_of=bob), lent, pytest.raises(ModelNotFoundError):
        registry.resolve_ref("embedding", kind="embedding", action="Embed")


def test_the_models_an_agent_was_built_with_are_read_from_their_gates(world):
    _h, _registry, _bob, large, small = world
    assert gated_model_ids(large) == {"large"}
    assert gated_model_ids(small) == {"small"}
    assert gated_model_ids(FakeListChatModel(responses=["x"])) == set()
