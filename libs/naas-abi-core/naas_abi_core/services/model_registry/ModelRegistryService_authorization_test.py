"""The model registry authorizes every operation, in process and over NATS alike."""

from __future__ import annotations

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.tests.authorization_contract import (
    JWT_SECRET,
    AuthorizationContract,
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
    ModelRegistryNATS,
)
from naas_abi_core.services.model_registry.adapters.secondary.model_registry_client import (
    ModelRegistryNATSClient,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import ModelNotFoundError
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)

CHAT = "abi:-:-:model_registry:model/demo-chat"


def _registry() -> ModelRegistryService:
    registry = ModelRegistryService()
    registry.register(
        "demo-chat",
        ChatModel(
            model_id="fake",
            provider="demo",
            model=FakeListChatModel(responses=["answer"] * 20),
        ),
    )
    registry.register(
        "demo-embedding",
        EmbeddingModel(
            model_id="fake-embedding",
            provider="demo",
            model=DeterministicFakeEmbedding(size=4),
        ),
    )
    return registry


class ModelRegistryContract(AuthorizationContract):
    NOT_FOUND = (ModelNotFoundError,)

    @pytest.fixture
    def owner(self, contract_iam, tmp_path):
        return wire(_registry(), contract_iam)

    def primary(self, owner):
        return ModelRegistryNATS(owner, JWT_SECRET, owner="c0" * 16)

    def facade(self, nats_url, identity):
        return ModelRegistryNATSClient(
            ModelRegistryService(), nats_url, JWT_SECRET, identity=identity
        )

    def resource(self, owner):
        return CHAT


class TestResolve(ModelRegistryContract):
    ACTION = "model_registry:Resolve"

    def call(self, service):
        return service.get_chat_model("demo-chat")


class TestChat(ModelRegistryContract):
    """Chat needs Chat alone: in process on the model the registry handed out,
    over NATS on the chat endpoint."""

    ACTION = "model_registry:Chat"

    def prepare(self, owner):
        self.model = owner.get_chat_model("demo-chat").model

    def call(self, service):
        if isinstance(service, ModelRegistryNATSClient):
            from naas_abi_sdk.model_codec import encode_message

            return service._call(
                service.remote._client.chat(
                    pb.ChatRequest(
                        ref=pb.ModelRef(canonical_id="demo-chat", kind="chat"),
                        messages=[encode_message(HumanMessage("hi"))],
                    )
                )
            )
        return self.model.invoke("hi")


class TestEmbed(ModelRegistryContract):
    ACTION = "model_registry:Embed"

    def resource(self, owner):
        return "abi:-:-:model_registry:model/demo-embedding"

    def call(self, service):
        if isinstance(service, ModelRegistryNATSClient):
            return service._call(
                service.remote._client.embed(
                    pb.EmbedRequest(
                        ref=pb.ModelRef(
                            canonical_id="demo-embedding", kind="embedding"
                        ),
                        texts=["hi"],
                    )
                )
            )
        # In process an embedding model is used directly: its resolution is
        # what is checked, so the use is pinned through the endpoint's path.
        return service.resolve_ref("demo-embedding", kind="embedding", action="Embed")


def test_listing_shows_only_the_models_the_caller_may_list():
    iam = contract_iam()
    h = IAMHarness(iam)
    registry = wire(_registry(), iam)
    bob = h.user()
    h.grant(bob.id, statement("Allow", ["model_registry:ListModels"], [CHAT]))
    with h.as_(actor="api", on_behalf_of=bob):
        assert registry.list_canonical_ids() == ["demo-chat"]
        assert [cid for cid, _ in registry.list_registered_models()] == ["demo-chat"]
    with as_service_account("engine"):
        assert set(registry.list_canonical_ids()) == {"demo-chat", "demo-embedding"}


def test_a_model_resolved_for_one_caller_is_checked_for_whoever_invokes_it():
    """Agents are built once, at boot, as the engine: their model is checked on
    every invocation, in the context of the call invoking it."""
    iam = contract_iam()
    h = IAMHarness(iam)
    registry = wire(_registry(), iam)
    with as_service_account("engine"):
        model = registry.get_chat_model("demo-chat").model
        assert model.invoke("hi").content == "answer"
    bob, ada = h.user("bob"), h.user("ada")
    h.grant(ada.id, statement("Allow", ["model_registry:Chat"], [CHAT]))
    with h.as_(actor="api", on_behalf_of=ada):
        assert model.invoke("hi").content == "answer"
    with h.as_(actor="api", on_behalf_of=bob), pytest.raises(ModelNotFoundError):
        model.invoke("hi")
    # Resolving again attaches no second gate.
    with as_service_account("engine"):
        registry.get_chat_model("demo-chat")
    assert len(model.callbacks) == 1


def test_a_streamed_invocation_is_checked_too():
    iam = contract_iam()
    h = IAMHarness(iam)
    registry = wire(_registry(), iam)
    with as_service_account("engine"):
        model = registry.get_chat_model("demo-chat").model
    bob = h.user()
    h.grant(
        bob.id,
        statement("Allow", ["model_registry:Resolve"], [CHAT]),
        statement("Deny", ["model_registry:Chat"], [CHAT]),
    )
    with h.as_(actor="api", on_behalf_of=bob), pytest.raises(PermissionDeniedError):
        list(model.stream("hi"))


def test_an_unwired_registry_checks_nothing():
    registry = _registry()
    model = registry.get_chat_model("demo-chat").model
    assert model.invoke("hi").content == "answer"
