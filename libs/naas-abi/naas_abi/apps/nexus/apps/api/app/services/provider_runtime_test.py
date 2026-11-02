from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    Message,
    ProviderConfig,
    UnsafeProviderEndpointError,
    agent_event_chunk,
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


def test_a_tool_response_keeps_its_chat_source_opt_out() -> None:
    assert agent_event_chunk("tool_response", "rows", chat_source=False) == {
        "event": "tool_response",
        "output": "rows",
        "chat_source": False,
    }
    assert agent_event_chunk("tool_response", "rows", chat_source=True) == {
        "event": "tool_response",
        "output": "rows",
    }
    assert agent_event_chunk("tool_usage", "search", chat_source=False) == {
        "event": "tool_usage",
        "tool": "search",
    }


def test_agents_outside_the_roster_are_not_duplicated(monkeypatch) -> None:
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
        _duplicate_inprocess_agent,
    )
    from naas_abi_core.services.agent.Agent import Agent

    monkeypatch.delenv("ENV", raising=False)

    class Enabled(Agent):
        pass

    class Disabled(Agent):
        pass

    def make(cls: type[Agent], name: str, agents: list[Agent] | None = None) -> Agent:
        return cls(
            name=name,
            description=f"{name} agent.",
            chat_model=GenericFakeChatModel(messages=iter([])),
            tools=[],
            agents=agents,
            memory=InMemorySaver(),
        )

    template = make(
        Agent, "Abi", [make(Enabled, "Search"), make(Disabled, "Gmail")]
    )
    allowed = frozenset({f"{__name__}/Enabled"})

    agent = _duplicate_inprocess_agent(template, "thread", allowed)

    assert [sub.name for sub in agent._agents] == ["Search"]
    assert "transfer_to_Gmail" not in agent._tools_by_name
    assert "transfer_to_Gmail" in template._tools_by_name


def test_interleaved_workspaces_each_keep_their_own_roster(monkeypatch) -> None:
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
        _duplicate_inprocess_agent,
        _prune_inprocess_subagents_for_roster,
    )
    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

    monkeypatch.delenv("ENV", raising=False)

    class AbiAgent(Agent):
        pass

    class SearchAgent(Agent):
        pass

    class GmailAgent(Agent):
        pass

    def make(cls: type[Agent], name: str, agents: list[Agent] | None = None) -> Agent:
        return cls(
            name=name,
            description=f"{name} agent.",
            chat_model=GenericFakeChatModel(messages=iter([])),
            tools=[],
            agents=agents,
            memory=InMemorySaver(),
            configuration=AgentConfiguration(
                system_prompt="You are Abi.\n<agents>\n- every agent\n</agents>\nBe kind."
            ),
        )

    template = make(
        AbiAgent, "Abi", [make(SearchAgent, "Search"), make(GmailAgent, "Gmail")]
    )
    template_prompt = template.configuration.system_prompt
    roster_a = frozenset({f"{__name__}/SearchAgent"})
    roster_b = frozenset({f"{__name__}/GmailAgent"})

    # Both turns are set up before either is pruned, then pruned in turn.
    turn_a = _duplicate_inprocess_agent(template, "thread-a", roster_a)
    turn_b = _duplicate_inprocess_agent(template, "thread-b", roster_b)
    _prune_inprocess_subagents_for_roster(turn_a, roster_a)
    _prune_inprocess_subagents_for_roster(turn_b, roster_b)

    prompt_a = turn_a.configuration.get_system_prompt([])
    prompt_b = turn_b.configuration.get_system_prompt([])
    assert "- Search: Search agent." in prompt_a
    assert "Gmail" not in prompt_a
    assert "- Gmail: Gmail agent." in prompt_b
    assert "Search" not in prompt_b
    assert prompt_a.endswith("Be kind.")

    tools_a = {name for name in turn_a._tools_by_name if name.startswith("transfer_to_")}
    tools_b = {name for name in turn_b._tools_by_name if name.startswith("transfer_to_")}
    assert tools_a == {"transfer_to_Search"}
    assert tools_b == {"transfer_to_Gmail"}

    assert template.configuration.system_prompt == template_prompt
    assert {"transfer_to_Search", "transfer_to_Gmail"} <= set(template._tools_by_name)
