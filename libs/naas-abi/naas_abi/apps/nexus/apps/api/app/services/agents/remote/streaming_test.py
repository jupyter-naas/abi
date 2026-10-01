from __future__ import annotations

import asyncio

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.in_memory import (
    InMemoryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.contracts import RESEARCHER
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import RemoteAgentUnavailable
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.streaming import (
    stream_with_remote_agent,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message, ProviderConfig


class _Directory:
    def __init__(self, events=(), error=None):
        self.events, self.error, self.calls = list(events), error, []

    async def list_agents(self):
        return [RESEARCHER]

    async def stream(self, key, prompt, *, thread_id, invocation_id=None):
        self.calls.append((key, prompt, thread_id, invocation_id))
        if self.error:
            raise self.error
        for event in self.events:
            yield event


def _config():
    return ProviderConfig(
        id="remote-a", name="Remote", type="remote", enabled=True, model=RESEARCHER.key
    )


def _run(directory, preamble=None):
    messages = [
        Message(role="user", content="first"),
        Message(role="assistant", content="ok"),
        Message(role="user", content="what is JetStream?"),
    ]

    async def collect():
        return [
            chunk
            async for chunk in stream_with_remote_agent(
                messages,
                _config(),
                thread_id="conv-1",
                user_context_preamble=preamble,
                invocation_id="msg-1",
                directory=directory,
            )
        ]

    return asyncio.run(collect())


def test_sends_the_latest_user_message_with_the_preamble_on_the_conversation_thread():
    directory = _Directory([{"event": "done", "data": "[DONE]"}])

    _run(directory, preamble="You are helping Ada.")

    assert directory.calls == [
        (RESEARCHER.key, "You are helping Ada.\n\nwhat is JetStream?", "conv-1", "msg-1")
    ]


def test_maps_agent_events_like_in_process_agents():
    directory = _Directory(
        [
            {"event": "tool_usage", "data": "search"},
            {"event": "tool_response", "data": "3 hits"},
            {"event": "ai_message", "data": "JetStream persists streams."},
            {"event": "message", "data": "JetStream persists streams."},
            {"event": "done", "data": "[DONE]"},
        ]
    )

    assert _run(directory) == [
        {"event": "tool_usage", "tool": "search"},
        {"event": "tool_response", "output": "3 hits"},
        "JetStream persists streams.",
    ]


def test_sdk_agents_that_only_send_message_events_still_answer():
    answer = [{"event": "message", "data": "line 1"}, {"event": "message", "data": "line 2"}]

    assert _run(_Directory([*answer, {"event": "done", "data": "[DONE]"}])) == ["line 1\nline 2"]


def test_unavailable_agent_becomes_an_error_message():
    chunks = _run(_Directory(error=RemoteAgentUnavailable(RESEARCHER.key, "MODULE_UNAVAILABLE")))

    assert len(chunks) == 1
    assert "**Error:**" in chunks[0] and "MODULE_UNAVAILABLE" in chunks[0]


def test_works_with_the_in_memory_directory():
    async def answer(prompt, thread_id):
        return f"fact: {prompt}"

    assert _run(InMemoryRemoteAgentDirectory({RESEARCHER: answer})) == ["fact: what is JetStream?"]
