"""Stream a Nexus chat turn to an agent published by a remote module."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    RemoteAgentDirectory,
    RemoteAgentUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    Message,
    ProviderConfig,
    agent_event_chunk,
)


async def stream_with_remote_agent(
    messages: list[Message],
    config: ProviderConfig,
    thread_id: str,
    *,
    user_context_preamble: str | None,
    invocation_id: str | None,
    directory: RemoteAgentDirectory | None = None,
) -> AsyncGenerator[str | dict[str, Any], None]:
    """Same prompt and event contract as ``stream_with_abi_inprocess``.

    ``config.model`` is the agent's ``class_name`` (``<module_id>/<Agent>``).
    ``thread_id`` is the conversation id, so the provider keeps one thread per
    conversation. ``invocation_id`` (the assistant message id) makes a retried
    submit idempotent. Only the prompt crosses NATS: the caller's context vars
    (user, workspace, open document) do not reach the remote agent.
    """
    if directory is None:
        from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
            get_remote_agent_directory,
        )

        directory = get_remote_agent_directory()

    prompt = next((m.content for m in reversed(messages) if m.role == "user"), None)
    if not prompt:
        yield "Error: No user message to send"
        return
    if user_context_preamble:
        prompt = f"{user_context_preamble.strip()}\n\n{prompt}"

    emitted = False
    final_replay: list[str] = []
    try:
        async for event in directory.stream(
            config.model, prompt, thread_id=thread_id, invocation_id=invocation_id
        ):
            name, text = event.get("event", ""), str(event.get("data") or "")
            if name == "done" or text == "[DONE]":
                break
            if name == "message":
                if text.strip():
                    final_replay.append(text.strip())
                continue
            chunk = agent_event_chunk(name, text)
            if chunk is not None:
                emitted = emitted or isinstance(chunk, str)
                yield chunk
    except RemoteAgentUnavailable as exc:
        yield f"\n\n**Error:** {exc}"
        return

    # SDK-only agents may answer with ``message`` events alone.
    if not emitted and final_replay:
        yield "\n".join(final_replay)
