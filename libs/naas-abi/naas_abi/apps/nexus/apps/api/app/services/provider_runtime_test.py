from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    Message,
    ProviderConfig,
    UnsafeProviderEndpointError,
    cloud_turn_tool_schema,
    complete_chat,
    openai_compatible_payload,
    redact_url_for_logs,
    stream_with_openai_compatible,
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


@pytest.mark.asyncio
async def test_inprocess_abi_turn_attaches_read_workspace_skill(monkeypatch) -> None:
    class _Model:
        def bind_tools(self, tools):
            bound = _Model()
            bound.names = [tool.name for tool in tools]
            return bound

    class _Agent:
        def __init__(self) -> None:
            self._tools_by_name: dict = {}
            self._structured_tools: list = []
            self._tools: list = []
            self._original_tools: list = []
            self._native_tools: list = []
            self._chat_model = _Model()
            self._chat_model_with_tools = None
            self._chat_model_without_workspace_tools = None

        def duplicate(self, queue=None, agent_shared_state=None):
            del queue, agent_shared_state
            return self

        async def ainvoke(self, prompt: str, thread_id: str | None = None) -> str:
            del prompt, thread_id
            return "ok"

    agent = _Agent()
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.provider_runtime._resolve_inprocess_abi_agent",
        lambda _model: agent,
    )

    await complete_chat(
        [Message(role="user", content="hello")],
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
        injection_preamble=None,
    )

    assert "read_workspace_skill" in agent._tools_by_name
    assert "create_skill" in agent._tools_by_name
    assert "write_file" not in agent._tools_by_name
    bound = agent._chat_model_without_workspace_tools
    assert bound is not None
    assert "read_workspace_skill" in bound.names
    assert "create_skill" in bound.names
    assert "write_file" not in bound.names


def test_cloud_turn_tool_schema_includes_read_workspace_skill() -> None:
    names = [item["function"]["name"] for item in cloud_turn_tool_schema()]
    assert names == ["read_workspace_skill", "create_skill"]
    assert "write_file" not in names
    create = next(
        item for item in cloud_turn_tool_schema() if item["function"]["name"] == "create_skill"
    )
    assert create["function"]["parameters"]["required"] == ["name", "prompt"]
    payload = openai_compatible_payload(
        [Message(role="user", content="hello")],
        ProviderConfig(
            id="p1",
            name="OpenAI",
            type="openai",
            enabled=True,
            endpoint="https://api.openai.com/v1",
            api_key="k",
            account_id=None,
            model="gpt-4o-mini",
        ),
        "system",
        stream=True,
    )
    assert payload["tools"] == cloud_turn_tool_schema()
    assert "hello" in payload["messages"][-1]["content"]


def test_chat_turn_tools_do_not_offer_a_home_skills_write() -> None:
    """write_skill_package is not a chat tool, and neither is a home skills path."""
    import json
    import re

    from naas_abi.tools.skills_tools import (
        make_create_skill_tool,
        make_read_workspace_skill_tool,
        skills_tools,
    )

    home_skills = re.compile(r"~/skills(?:/|$)|skills/<slug>/SKILL\.md|(?<![A-Za-z0-9_./-])skills/")
    entries: list[tuple[str, str]] = []
    for item in cloud_turn_tool_schema():
        function = item["function"]
        entries.append((function["name"], json.dumps(function)))
    for tool in (
        *skills_tools(),
        make_read_workspace_skill_tool(),
        make_create_skill_tool(),
    ):
        entries.append(
            (
                tool.name,
                f"{tool.description or ''}\n{json.dumps(getattr(tool, 'args', {}))}",
            )
        )
    offenders = [
        name
        for name, blob in entries
        if name in {"write_file", "write_skill_package"} or home_skills.search(blob)
    ]
    assert offenders == []


def _sse(payload: dict) -> str:
    import json

    return "data: " + json.dumps(payload)


def _tool_call_stream(slug: str) -> list[str]:
    return [
        _sse(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_skill",
                                    "type": "function",
                                    "function": {
                                        "name": "read_workspace_skill",
                                        "arguments": "",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ),
        _sse(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '{"slug": "' + slug + '"}'},
                                }
                            ]
                        }
                    }
                ]
            }
        ),
        _sse({"choices": [{"finish_reason": "tool_calls", "delta": {}}]}),
        "data: [DONE]",
    ]


@pytest.mark.asyncio
async def test_cloud_stream_executes_read_workspace_skill(monkeypatch) -> None:
    """A cloud tool call runs read_workspace_skill and the next request carries the body."""
    import asyncio
    import contextlib
    import json
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

    from naas_abi.agents.feature.context import nexus_feature_context
    from naas_abi.apps.nexus.apps.api.app.services.skills.port import SkillRecord
    from naas_abi.tools import skills_tools as tools_module

    enabled_body = "ENABLED_SKILL_BODY_MUST_REACH_THE_MODEL"
    disabled_body = "DISABLED_BODY_MUST_STAY_HIDDEN"
    now = datetime(2026, 9, 17, tzinfo=UTC)

    def _skill(skill_id: str, slug: str, *, prompt: str, enabled: bool = True) -> SkillRecord:
        return SkillRecord(
            id=skill_id,
            workspace_id="ws-1",
            organization_id=None,
            user_id="user-1",
            name=slug,
            slug=slug,
            description="",
            prompt=prompt,
            scope="user",
            enabled=enabled,
            last_used_at=None,
            created_at=now,
            updated_at=now,
        )

    class _Skills:
        def __init__(self) -> None:
            self.skills = [
                _skill("skill-1", "weekly-report", prompt=enabled_body),
                _skill("skill-off", "disabled-one", prompt=disabled_body, enabled=False),
            ]

        async def list_visible_skills(self, context, workspace_id):
            del context, workspace_id
            return list(self.skills)

    service = _Skills()

    def _run_db(fn):
        def _go():
            return asyncio.run(fn(object()))

        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_go).result()

    async def _require_member(db, user_id, workspace_id):
        del db, user_id, workspace_id
        return "owner"

    monkeypatch.setattr(tools_module, "run_db", _run_db)
    monkeypatch.setattr(tools_module, "require_member", _require_member)
    monkeypatch.setattr(tools_module, "request_context", lambda user_id: user_id)
    monkeypatch.setattr(tools_module, "bound_session", lambda db: contextlib.nullcontext())
    monkeypatch.setattr(tools_module, "_registry", lambda: SimpleNamespace(skills=service))

    requests: list[dict] = []

    class _Response:
        def __init__(self, lines: list[str]) -> None:
            self.status_code = 200
            self._lines = lines

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def aiter_lines(self):
            for line in self._lines:
                yield line

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, method, url, headers=None, json=None):
            del method, url, headers
            requests.append(json)
            if len(requests) == 1:
                slug = "weekly-report"
                return _Response(_tool_call_stream(slug))
            return _Response(
                [
                    _sse({"choices": [{"delta": {"content": "followed the skill"}}]}),
                    "data: [DONE]",
                ]
            )

    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.provider_runtime.httpx.AsyncClient",
        _Client,
    )
    user = agent_user_id.set("user-1")
    workspace = agent_workspace_id.set("ws-1")
    feature = nexus_feature_context.set(None)
    config = ProviderConfig(
        id="p1",
        name="OpenAI",
        type="openai",
        enabled=True,
        endpoint="https://api.openai.com/v1",
        api_key="test-key",
        account_id=None,
        model="gpt-4o-mini",
    )
    try:
        chunks: list[str] = []
        async for chunk in stream_with_openai_compatible(
            [Message(role="user", content="use the weekly report skill")],
            config,
            "system",
        ):
            chunks.append(chunk)
    finally:
        agent_user_id.reset(user)
        agent_workspace_id.reset(workspace)
        nexus_feature_context.reset(feature)

    assert len(requests) >= 2
    follow = json.dumps(requests[1])
    assert enabled_body in follow
    assert "".join(chunks) == "followed the skill"
    assert disabled_body not in follow

    async def _hidden(slug: str) -> str:
        requests.clear()

        class _HiddenClient(_Client):
            def stream(self, method, url, headers=None, json=None):
                del method, url, headers
                requests.append(json)
                if len(requests) == 1:
                    return _Response(_tool_call_stream(slug))
                return _Response(
                    [
                        _sse({"choices": [{"delta": {"content": "no body"}}]}),
                        "data: [DONE]",
                    ]
                )

        monkeypatch.setattr(
            "naas_abi.apps.nexus.apps.api.app.services.provider_runtime.httpx.AsyncClient",
            _HiddenClient,
        )
        hidden_user = agent_user_id.set("user-1")
        hidden_workspace = agent_workspace_id.set("ws-1")
        try:
            text: list[str] = []
            async for chunk in stream_with_openai_compatible(
                [Message(role="user", content=f"read {slug}")],
                config,
                "system",
            ):
                text.append(chunk)
        finally:
            agent_user_id.reset(hidden_user)
            agent_workspace_id.reset(hidden_workspace)
        blob = json.dumps(requests) + "".join(text)
        assert enabled_body not in blob
        assert disabled_body not in blob
        return blob

    await _hidden("disabled-one")
    await _hidden("not-a-skill")
    await _hidden("create-skill")


def test_redact_url_for_logs_masks_sensitive_query_params() -> None:
    url = "https://api.example.com/stream?token=secret123&foo=bar&api_key=xyz"
    redacted = redact_url_for_logs(url)

    assert "token=REDACTED" in redacted
    assert "api_key=REDACTED" in redacted
    assert "foo=bar" in redacted
    assert "secret123" not in redacted
    assert "xyz" not in redacted
