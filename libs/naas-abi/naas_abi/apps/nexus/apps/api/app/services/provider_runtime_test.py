from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig,
    UnsafeProviderEndpointError,
    redact_url_for_logs,
    validated_provider_endpoint,
)


def test_custom_endpoint_rejects_localhost() -> None:
    config = ProviderConfig(
        id="p1",
        name="Custom",
        type="custom",
        enabled=True,
        endpoint="http://127.0.0.1:8000",
        api_key="k",
        account_id=None,
        model="gpt-4o-mini",
    )

    with pytest.raises(UnsafeProviderEndpointError):
        validated_provider_endpoint(config)


def test_custom_endpoint_accepts_public_https() -> None:
    config = ProviderConfig(
        id="p1",
        name="Custom",
        type="custom",
        enabled=True,
        endpoint="https://api.example.com/v1",
        api_key="k",
        account_id=None,
        model="gpt-4o-mini",
    )

    assert validated_provider_endpoint(config) == "https://api.example.com/v1"


def test_openai_endpoint_rejects_non_official_host() -> None:
    config = ProviderConfig(
        id="p1",
        name="OpenAI",
        type="openai",
        enabled=True,
        endpoint="https://evil.example.com/v1",
        api_key="k",
        account_id=None,
        model="gpt-4o-mini",
    )

    with pytest.raises(UnsafeProviderEndpointError):
        validated_provider_endpoint(config)


def test_openai_endpoint_defaults_to_official_url() -> None:
    config = ProviderConfig(
        id="p1",
        name="OpenAI",
        type="openai",
        enabled=True,
        endpoint=None,
        api_key="k",
        account_id=None,
        model="gpt-4o-mini",
    )

    assert validated_provider_endpoint(config) == "https://api.openai.com/v1"


def test_ollama_endpoint_allows_localhost() -> None:
    config = ProviderConfig(
        id="p1",
        name="Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://localhost:11434",
        api_key=None,
        account_id=None,
        model="qwen3-vl:2b",
    )

    assert validated_provider_endpoint(config) == "http://localhost:11434"


def test_redact_url_for_logs_masks_sensitive_query_params() -> None:
    url = "https://api.example.com/stream?token=secret123&foo=bar&api_key=xyz"
    redacted = redact_url_for_logs(url)

    assert "token=REDACTED" in redacted
    assert "api_key=REDACTED" in redacted
    assert "foo=bar" in redacted
    assert "secret123" not in redacted
    assert "xyz" not in redacted
