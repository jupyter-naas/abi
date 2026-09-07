from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    Message,
    ProviderConfig,
    UnsafeProviderEndpointError,
    complete_chat,
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
        model="qwen2.5:3b",
    )

    assert validated_provider_endpoint(config) == "http://localhost:11434"


def test_ollama_endpoint_allows_wsl_gateway_private_ip() -> None:
    """WSL NAT: resolve_endpoint() returns the Windows host as a private IP."""
    config = ProviderConfig(
        id="p1",
        name="Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://172.22.80.1:11434",
        api_key=None,
        account_id=None,
        model="qwen2.5:3b",
    )

    assert validated_provider_endpoint(config) == "http://172.22.80.1:11434"


def test_ollama_endpoint_allows_host_docker_internal() -> None:
    config = ProviderConfig(
        id="p1",
        name="Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://host.docker.internal:11434",
        api_key=None,
        account_id=None,
        model="qwen2.5:3b",
    )

    assert (
        validated_provider_endpoint(config) == "http://host.docker.internal:11434"
    )


def test_ollama_endpoint_still_rejects_cloud_metadata_ip() -> None:
    config = ProviderConfig(
        id="p1",
        name="Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://169.254.169.254:11434",
        api_key=None,
        account_id=None,
        model="qwen2.5:3b",
    )

    with pytest.raises(UnsafeProviderEndpointError):
        validated_provider_endpoint(config)


def test_custom_endpoint_still_rejects_private_lan_ip() -> None:
    config = ProviderConfig(
        id="p1",
        name="Custom",
        type="custom",
        enabled=True,
        endpoint="http://172.22.80.1:8000",
        api_key="k",
        account_id=None,
        model="gpt-4o-mini",
    )

    with pytest.raises(UnsafeProviderEndpointError):
        validated_provider_endpoint(config)


@pytest.mark.asyncio
async def test_complete_chat_carries_the_injection_preamble_into_the_abi_agent(
    monkeypatch,
) -> None:
    """The preamble has to arrive on the prompt the agent actually runs.

    ABI agents build their own system prompt and ignore the Nexus
    ``system_prompt``, so prepending the preamble to the latest user message is
    the only channel carrying the skills catalog and the user profile. Every
    other test on this path stops at a double: ``service_test`` asserts
    ``complete_chat_request`` hands the preamble to the provider function, and
    the provider function is replaced there. Nothing read it off the prompt the
    agent received, so ``complete_chat`` could route to ``complete_with_abi``
    without the argument, or ``complete_with_abi`` could stop prepending, and
    the suite would stay green while the agent lost the catalog.
    """

    class _Agent:
        def __init__(self) -> None:
            self.prompt: str | None = None

        async def ainvoke(self, prompt: str, thread_id: str | None = None) -> str:
            self.prompt = prompt
            return "assistant answer"

    agent = _Agent()
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.provider_runtime._resolve_inprocess_abi_agent",
        lambda _model: agent,
    )

    answer = await complete_chat(
        [Message(role="user", content="brief me on the strait of hormuz")],
        ProviderConfig(
            id="p1",
            name="Abi",
            type="abi",
            enabled=True,
            endpoint="inprocess://abi",
            api_key=None,
            account_id=None,
            model="Abi",
        ),
        None,
        thread_id="conv-1",
        injection_preamble="You can call create_skill.",
    )

    assert answer == "assistant answer"
    assert agent.prompt == "You can call create_skill.\n\nbrief me on the strait of hormuz"


def test_redact_url_for_logs_masks_sensitive_query_params() -> None:
    url = "https://api.example.com/stream?token=secret123&foo=bar&api_key=xyz"
    redacted = redact_url_for_logs(url)

    assert "token=REDACTED" in redacted
    assert "api_key=REDACTED" in redacted
    assert "foo=bar" in redacted
    assert "secret123" not in redacted
    assert "xyz" not in redacted
