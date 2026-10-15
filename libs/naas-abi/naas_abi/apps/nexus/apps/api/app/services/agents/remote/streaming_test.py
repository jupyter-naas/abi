from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.in_memory import (
    InMemoryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.contracts import RESEARCHER
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import RemoteAgentUnavailable
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.streaming import (
    NoUserMessage,
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


def test_a_chat_completion_joins_the_remote_agents_text(monkeypatch):
    # POST /api/chat/complete: the same stream, its text without the steps.
    from naas_abi.apps.nexus.apps.api.app.services import provider_runtime
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote import factory

    directory = _Directory(
        [
            {"event": "ai_message", "data": "Jet"},
            {"event": "tool_usage", "data": "search"},
            {"event": "ai_message", "data": "Stream"},
            {"event": "done", "data": "[DONE]"},
        ]
    )
    monkeypatch.setattr(factory, "get_remote_agent_directory", lambda: directory)

    text = asyncio.run(
        provider_runtime.complete_chat(
            [Message(role="user", content="what is JetStream?")],
            _config(),
            None,
            thread_id="conv-1",
            injection_preamble="USER PROFILE",
        )
    )

    assert text == "JetStream"
    assert directory.calls == [
        (RESEARCHER.key, "USER PROFILE\n\nwhat is JetStream?", "conv-1", None)
    ]


def test_the_stream_reads_on_to_the_runs_end_after_done():
    # Breaking out at done closed the directory's stream, which cancels the
    # run while the module still holds the conversation.
    finished = []

    class _Draining(_Directory):
        async def stream(self, key, prompt, *, thread_id, invocation_id=None):
            async for event in super().stream(
                key, prompt, thread_id=thread_id, invocation_id=invocation_id
            ):
                yield event
            finished.append(True)

    chunks = _run(
        _Draining(
            [{"event": "ai_message", "data": "hi"}, {"event": "done", "data": "[DONE]"}]
        )
    )

    assert chunks == ["hi"]
    assert finished == [True]


def _complete(monkeypatch, directory, messages=None):
    from naas_abi.apps.nexus.apps.api.app.services import provider_runtime
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote import factory

    monkeypatch.setattr(factory, "get_remote_agent_directory", lambda: directory)
    return asyncio.run(
        provider_runtime.complete_chat(
            messages or [Message(role="user", content="what is JetStream?")],
            _config(),
            None,
            thread_id="conv-1",
            injection_preamble=None,
        )
    )


def test_a_chat_completion_raises_when_the_agent_is_unavailable(monkeypatch):
    # Not a 200 whose stored answer is the error text: the service marks the
    # provider "(error)", as for an in-process agent.
    unavailable = _Directory(error=RemoteAgentUnavailable(RESEARCHER.key, "NO_RESPONDERS"))
    with pytest.raises(RemoteAgentUnavailable, match="NO_RESPONDERS"):
        _complete(monkeypatch, unavailable)


def test_a_chat_completion_without_a_user_message_raises(monkeypatch):
    with pytest.raises(NoUserMessage):
        _complete(monkeypatch, _Directory(), [Message(role="assistant", content="hi")])


class _FailsAfterDone(_Directory):
    """A run whose answer is done, then ends FAILED while the module saves it."""

    async def stream(self, key, prompt, *, thread_id, invocation_id=None):
        yield {"event": "ai_message", "data": "JetStream"}
        yield {"event": "done", "data": "[DONE]"}
        raise RemoteAgentUnavailable(key, "AGENT_FAILED")


def test_a_failure_after_done_leaves_the_answer_as_it_was(monkeypatch, caplog):
    assert _run(_FailsAfterDone()) == ["JetStream"]
    assert "AGENT_FAILED" in caplog.text
    assert _complete(monkeypatch, _FailsAfterDone()) == "JetStream"


def test_a_failure_before_done_still_ends_the_stream_with_an_error():
    class _FailsMidway(_Directory):
        async def stream(self, key, prompt, *, thread_id, invocation_id=None):
            yield {"event": "ai_message", "data": "Jet"}
            raise RemoteAgentUnavailable(key, "WAIT_TIMEOUT")

    chunks = _run(_FailsMidway())

    assert chunks[0] == "Jet"
    assert "**Error:**" in chunks[1] and "WAIT_TIMEOUT" in chunks[1]
