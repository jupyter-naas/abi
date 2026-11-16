"""The Azure AI Foundry clients: Entra ID token wiring, API key fallback, and
what goes over the wire. Requests are answered in-process (``http_requests``)."""

from __future__ import annotations

import sys
from typing import Any

import httpx
import pytest
from naas_abi_marketplace.ai.azure.foundry import (
    DEFAULT_TOKEN_SCOPE,
    PROVIDER,
    AzureAuth,
    AzureChatDeployment,
    AzureEmbeddingDeployment,
    chat_client,
    chat_model,
    embedding_client,
    embedding_model,
    entra_id_token_provider,
)
from pydantic import SecretStr, ValidationError

TOKEN = "entra-id-token-for-tests"
ENDPOINT = "https://example-resource.openai.azure.com/"
API_VERSION = "2024-10-21"


def test_token_provider_uses_default_credential_and_cognitive_services_scope(
    fake_identity: Any,
) -> None:
    provider = entra_id_token_provider()

    assert fake_identity.credentials == [{}]
    assert fake_identity.scopes == [(DEFAULT_TOKEN_SCOPE,)]
    assert DEFAULT_TOKEN_SCOPE == "https://cognitiveservices.azure.com/.default"
    assert provider() == fake_identity.token


def test_token_provider_selects_a_user_assigned_managed_identity(
    fake_identity: Any,
) -> None:
    entra_id_token_provider("11111111-2222-3333-4444-555555555555")

    assert fake_identity.credentials == [
        {"managed_identity_client_id": "11111111-2222-3333-4444-555555555555"}
    ]


def test_token_provider_without_client_id_leaves_azure_client_id_to_the_sdk(
    fake_identity: Any,
) -> None:
    """Passing managed_identity_client_id=None would override AZURE_CLIENT_ID."""
    entra_id_token_provider(None)
    entra_id_token_provider("")

    assert fake_identity.credentials == [{}, {}]


def test_token_provider_honours_a_custom_scope(fake_identity: Any) -> None:
    entra_id_token_provider(scope="https://cognitiveservices.azure.us/.default")

    assert fake_identity.scopes == [("https://cognitiveservices.azure.us/.default",)]


def test_missing_azure_identity_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "azure.identity", None)

    with pytest.raises(ImportError, match=r"naas-abi-marketplace\[ai-azure\]"):
        entra_id_token_provider()


def test_auth_takes_exactly_one_method() -> None:
    with pytest.raises(ValueError):
        AzureAuth()
    with pytest.raises(ValueError):
        AzureAuth(api_key=SecretStr("k"), token_provider=lambda: TOKEN)


def test_chat_request_carries_the_bearer_token_and_no_key(
    http_requests: list[httpx.Request],
) -> None:
    calls: list[int] = []

    def provider() -> str:
        calls.append(1)
        return TOKEN

    client = chat_client(
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        deployment="gpt-4o-prod",
        auth=AzureAuth(token_provider=provider),
    )
    assert client.azure_ad_token_provider is provider
    assert client.openai_api_key is None

    reply = client.invoke("ping")

    assert reply.content == "pong"
    assert calls, "the token provider was not called"
    (request,) = http_requests
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "api-key" not in request.headers
    assert request.url.host == "example-resource.openai.azure.com"
    assert request.url.path == "/openai/deployments/gpt-4o-prod/chat/completions"
    assert request.url.params["api-version"] == API_VERSION


def test_an_openai_key_in_the_environment_is_not_picked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-unrelated")

    client = chat_client(
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        deployment="gpt-4o-prod",
        auth=AzureAuth(token_provider=lambda: TOKEN),
    )

    assert client.openai_api_key is None


def test_chat_request_with_an_api_key_sends_the_key(
    http_requests: list[httpx.Request],
) -> None:
    client = chat_client(
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        deployment="gpt-4o-prod",
        auth=AzureAuth(api_key=SecretStr("azure-key")),
    )

    client.invoke("ping")

    (request,) = http_requests
    assert request.headers["api-key"] == "azure-key"
    # The openai SDK also mirrors a key into "Authorization: Bearer <key>":
    # what matters is that no Entra ID token is involved.
    assert request.headers.get("Authorization") in (None, "Bearer azure-key")


def test_embedding_request_carries_the_bearer_token(
    http_requests: list[httpx.Request],
) -> None:
    client = embedding_client(
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        deployment="embeddings-large",
        auth=AzureAuth(token_provider=lambda: TOKEN),
        model_name="text-embedding-3-large",
        dimensions=1024,
    )

    # The OpenAI client directly: embed_query would tokenize with tiktoken
    # first, which downloads its encoding.
    client.client.create(input=["hello"], model="text-embedding-3-large")

    (request,) = http_requests
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "api-key" not in request.headers
    assert request.url.path == "/openai/deployments/embeddings-large/embeddings"
    assert client.dimensions == 1024


def test_chat_model_metadata() -> None:
    deployment = AzureChatDeployment(
        deployment="gpt-4o-prod",
        canonical_id="gpt-4o",
        model_name="gpt-4o",
        context_window=128000,
        temperature=0,
    )

    model = chat_model(
        deployment,
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        auth=AzureAuth(token_provider=lambda: TOKEN),
    )

    assert model.provider == PROVIDER == "azure"
    assert model.model_id == "gpt-4o-prod"
    assert model.context_window == 128000
    assert model.name == "gpt-4o"
    client = model.model
    assert getattr(client, "deployment_name", None) == "gpt-4o-prod"
    assert getattr(client, "model_name", None) == "gpt-4o"
    assert getattr(client, "temperature", None) == 0


def test_chat_model_sends_no_temperature_unless_configured() -> None:
    """Reasoning deployments (o-series, gpt-5) refuse a temperature."""
    model = chat_model(
        AzureChatDeployment(deployment="o4-mini"),
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        auth=AzureAuth(token_provider=lambda: TOKEN),
    )

    assert getattr(model.model, "temperature", None) is None


def test_a_deployment_endpoint_overrides_the_module_endpoint() -> None:
    model = embedding_model(
        AzureEmbeddingDeployment(
            deployment="embeddings-small",
            endpoint="https://other-region.openai.azure.com/",
        ),
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        auth=AzureAuth(token_provider=lambda: TOKEN),
    )

    assert (
        getattr(model.model, "azure_endpoint", None)
        == "https://other-region.openai.azure.com/"
    )


def test_embedding_model_metadata() -> None:
    model = embedding_model(
        AzureEmbeddingDeployment(
            deployment="embeddings-large",
            canonical_id="text-embedding-3-large",
            dimensions=3072,
        ),
        endpoint=ENDPOINT,
        api_version=API_VERSION,
        auth=AzureAuth(token_provider=lambda: TOKEN),
    )

    assert model.provider == "azure"
    assert model.model_id == "embeddings-large"
    assert model.dimensions == 3072


def test_deployment_entries_reject_unknown_and_blank_fields() -> None:
    with pytest.raises(ValidationError):
        AzureChatDeployment(deployment="gpt-4o-prod", deployment_id="typo")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        AzureChatDeployment(deployment="  ")
    entry = AzureChatDeployment(deployment="gpt-4o-prod", canonical_id="")
    assert entry.registry_id == "gpt-4o-prod"
