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

    assert validated_provider_endpoint(config) == "http://host.docker.internal:11434"


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


def _agents():
    """A lead with a helper (that has a hidden sub-agent) and a hidden
    sub-agent, each of its own class: the runtime keeps agents by class."""
    from langgraph.checkpoint.memory import MemorySaver
    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
    from naas_abi_core.services.agent.Agent_keep_subagents_test import _Model, lookup

    class Lead(Agent):
        pass

    class Helper(Agent):
        pass

    class Hidden(Agent):
        pass

    def make(cls, name, agents=()):
        return cls(
            name=name,
            description=name,
            chat_model=_Model(),
            tools=[lookup],
            agents=list(agents),
            memory=MemorySaver(),
            state=AgentSharedState(thread_id="t"),
            configuration=AgentConfiguration(system_prompt=name),
            enable_default_tools=False,
        )

    helper = make(Helper, "Helper", [make(Hidden, "DeepHidden")])
    return make(Lead, "Lead", [helper, make(Hidden, "Hidden")]), helper


def test_a_turn_runs_only_the_agents_its_caller_may_use() -> None:
    """The route binds the caller's usable agents; the in-process runtime runs
    no other, and its copy of the agent leaves the rest out at every depth:
    no handoff tool, no bound tool, no graph node."""
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
        _inprocess_agent_class_name,
        _turn_copy,
    )
    from naas_abi_core.services.agent.context import agent_workspace_enabled_class_names

    lead, helper = _agents()
    hidden = lead._original_agents[1]
    allowed = frozenset(_inprocess_agent_class_name(a) for a in (lead, helper))

    token = agent_workspace_enabled_class_names.set(allowed)
    try:
        copy = _turn_copy(lead, "t-1")
        assert copy is not None and copy is not lead
        assert [a.name for a in copy._agents] == ["Helper"]
        assert "transfer_to_Hidden" not in copy._tools_by_name
        assert "transfer_to_Hidden" not in copy._chat_model_with_tools.bound
        assert "Hidden" not in set(copy.graph.get_graph().nodes)
        (helper_copy,) = copy._agents
        assert (
            helper_copy._agents == [] and "transfer_to_DeepHidden" not in helper_copy._tools_by_name
        )
        assert _turn_copy(hidden, "t-1") is None
        agent_workspace_enabled_class_names.set(frozenset())
        assert _turn_copy(lead, "t-1") is None
    finally:
        agent_workspace_enabled_class_names.reset(token)
    # A caller outside Nexus's routes: nothing is narrowed.
    assert [a.name for a in _turn_copy(lead, "t-1")._agents] == ["Helper", "Hidden"]
