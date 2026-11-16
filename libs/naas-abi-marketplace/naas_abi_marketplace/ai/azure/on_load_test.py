"""The azure module's configuration and what ``on_load`` registers: chat and
embedding deployments from the config, no API key needed, one Entra ID token
provider shared by every client. No network and no Azure account."""

from __future__ import annotations

from typing import Any, cast

import httpx
import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from pydantic import ValidationError

ENDPOINT = "https://example-resource.openai.azure.com/"

DEPLOYMENTS: dict[str, Any] = {
    "endpoint": ENDPOINT,
    "chat_deployments": [
        {
            "deployment": "gpt-4o-prod",
            "canonical_id": "gpt-4o",
            "model_name": "gpt-4o",
            "context_window": 128000,
        },
        {"deployment": "gpt-4o-mini-prod"},
    ],
    "embedding_deployments": [
        {
            "deployment": "embeddings-large",
            "canonical_id": "text-embedding-3-large",
            "dimensions": 3072,
        }
    ],
}


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def _configuration(**config: Any):
    from naas_abi_marketplace.ai.azure import ABIModule

    return ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"), **config
    )


def _make_module(**config: Any):
    from naas_abi_marketplace.ai.azure import ABIModule

    registry = ModelRegistryService()
    engine = _DummyEngine(services=IEngine.Services(model_registry=registry))
    proxy = EngineProxy(
        # Only ``services`` and ``modules`` are read during on_load.
        engine=cast(IEngine, engine),
        module_name="naas_abi_marketplace.ai.azure",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    return ABIModule(proxy, _configuration(**config)), registry


# --------------------------------------------------------------- configuration


def test_configuration_needs_no_api_key() -> None:
    cfg = _configuration(**DEPLOYMENTS)

    assert cfg.azure_api_key is None
    assert cfg.managed_identity_client_id is None
    assert cfg.api_version == "2024-10-21"
    assert cfg.token_scope == "https://cognitiveservices.azure.com/.default"
    assert [d.registry_id for d in cfg.chat_deployments] == [
        "gpt-4o",
        "gpt-4o-mini-prod",
    ]
    assert cfg.embedding_deployments[0].dimensions == 3072


def test_unset_secrets_render_blank_and_count_as_unset() -> None:
    cfg = _configuration(
        **DEPLOYMENTS, azure_api_key="", managed_identity_client_id="  "
    )

    assert cfg.azure_api_key is None
    assert cfg.managed_identity_client_id is None


def test_the_previous_key_only_configuration_still_loads() -> None:
    """Before deployments, the module took only azure_api_key."""
    cfg = _configuration(azure_api_key="legacy-key", datastore_path="azure")

    assert cfg.chat_deployments == []
    assert cfg.embedding_deployments == []


def test_a_deployment_without_an_endpoint_is_refused() -> None:
    with pytest.raises(ValidationError, match="no endpoint"):
        _configuration(chat_deployments=[{"deployment": "gpt-4o-prod"}])


def test_a_deployment_may_bring_its_own_endpoint() -> None:
    cfg = _configuration(
        embedding_deployments=[
            {"deployment": "e", "endpoint": "https://other.openai.azure.com/"}
        ]
    )

    assert cfg.endpoint_for(cfg.embedding_deployments[0]) == (
        "https://other.openai.azure.com/"
    )


def test_canonical_ids_must_be_unique_across_chat_and_embeddings() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        _configuration(
            endpoint=ENDPOINT,
            chat_deployments=[{"deployment": "shared"}],
            embedding_deployments=[{"deployment": "other", "canonical_id": "shared"}],
        )


def test_unknown_configuration_keys_are_refused() -> None:
    with pytest.raises(ValidationError):
        _configuration(**DEPLOYMENTS, endpont="typo")


# --------------------------------------------------------------------- on_load


def test_on_load_registers_chat_and_embedding_deployments(
    fake_identity: Any,
) -> None:
    module, registry = _make_module(**DEPLOYMENTS)
    module.on_load()

    assert {"gpt-4o", "gpt-4o-mini-prod", "text-embedding-3-large"} <= set(
        registry.list_canonical_ids()
    )

    chat = registry.get_chat_model("gpt-4o", provider="azure")
    assert isinstance(chat, ChatModel)
    assert chat.provider == "azure"
    assert chat.model_id == "gpt-4o-prod"
    assert chat.context_window == 128000

    unnamed = registry.get_chat_model("gpt-4o-mini-prod")
    assert unnamed.model_id == "gpt-4o-mini-prod"

    emb = registry.get_embedding_model("text-embedding-3-large", provider="azure")
    assert isinstance(emb, EmbeddingModel)
    assert emb.model_id == "embeddings-large"
    assert emb.dimensions == 3072


def test_on_load_without_a_key_uses_one_entra_id_token_provider(
    fake_identity: Any,
) -> None:
    module, registry = _make_module(
        **DEPLOYMENTS, managed_identity_client_id="client-id-of-the-identity"
    )
    module.on_load()

    # One credential for the module, scoped to Azure OpenAI.
    assert fake_identity.credentials == [
        {"managed_identity_client_id": "client-id-of-the-identity"}
    ]
    assert fake_identity.scopes == [("https://cognitiveservices.azure.com/.default",)]

    chat = registry.get_chat_model("gpt-4o").model
    emb = registry.get_embedding_model("text-embedding-3-large").model
    assert getattr(chat, "azure_ad_token_provider", None) == fake_identity.provider
    assert getattr(emb, "azure_ad_token_provider", None) == fake_identity.provider
    assert getattr(chat, "openai_api_key", "unset") is None
    assert getattr(emb, "openai_api_key", "unset") is None


def test_a_registered_chat_model_calls_azure_with_the_token(
    fake_identity: Any, http_requests: list[httpx.Request]
) -> None:
    module, registry = _make_module(**DEPLOYMENTS)
    module.on_load()

    reply = registry.get_chat_model("gpt-4o").model.invoke("ping")

    assert reply.content == "pong"
    assert fake_identity.token_calls >= 1
    (request,) = http_requests
    assert request.headers["Authorization"] == f"Bearer {fake_identity.token}"
    assert "api-key" not in request.headers
    assert request.url.path == "/openai/deployments/gpt-4o-prod/chat/completions"


def test_on_load_with_an_api_key_does_not_touch_azure_identity(
    no_identity: None, http_requests: list[httpx.Request]
) -> None:
    module, registry = _make_module(**DEPLOYMENTS, azure_api_key="azure-key")
    module.on_load()

    registry.get_chat_model("gpt-4o").model.invoke("ping")

    (request,) = http_requests
    assert request.headers["api-key"] == "azure-key"
    # The openai SDK also mirrors a key into "Authorization: Bearer <key>":
    # what matters is that no Entra ID token is involved.
    assert request.headers.get("Authorization") in (None, "Bearer azure-key")


def test_on_load_registers_factories_for_other_deployments(
    fake_identity: Any,
) -> None:
    module, registry = _make_module(**DEPLOYMENTS)
    module.on_load()

    chat = registry.get_chat_model("another-deployment", provider="azure")
    assert chat.model_id == "another-deployment"
    assert getattr(chat.model, "deployment_name", None) == "another-deployment"

    emb = registry.get_embedding_model("another-embedder", provider="azure")
    assert emb.model_id == "another-embedder"
    assert getattr(emb.model, "deployment", None) == "another-embedder"


def test_on_load_with_nothing_configured_registers_nothing(
    no_identity: None,
) -> None:
    module, registry = _make_module()
    module.on_load()

    assert registry.list_canonical_ids() == []


def test_on_load_with_the_real_azure_identity_stays_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Building the credential, token provider and clients opens no
    connection: the first token is fetched on the first model call."""
    import socket

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("on_load opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    module, registry = _make_module(**DEPLOYMENTS)
    module.on_load()

    chat = registry.get_chat_model("gpt-4o").model
    assert callable(getattr(chat, "azure_ad_token_provider", None))
