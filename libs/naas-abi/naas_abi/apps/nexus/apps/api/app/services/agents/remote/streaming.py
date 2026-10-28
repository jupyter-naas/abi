"""Stream a Nexus chat turn to an agent published by a remote module."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


class NoUserMessage(ValueError):
    """The turn holds no user message to send to the agent."""

    def __init__(self) -> None:
        super().__init__("No user message to send")


async def stream_with_remote_agent(
    messages: list[Message],
    config: ProviderConfig,
    thread_id: str,
    *,
    user_context_preamble: str | None,
    invocation_id: str | None,
    directory: RemoteAgentDirectory | None = None,
    workspace_id: str | None = None,
) -> AsyncGenerator[str | dict[str, Any], None]:
    """Same prompt and event contract as ``stream_with_abi_inprocess``.

    ``config.model`` is the agent's ``class_name`` (``<module_id>/<Agent>``).
    ``thread_id`` is the conversation id, so the provider keeps one thread per
    conversation. ``invocation_id`` (the assistant message id) makes a retried
    submit idempotent. Only the prompt crosses NATS: the caller's context vars
    (user, workspace, open document) do not reach the remote agent. A failure
    ends the stream as an error message in the chat.
    """
    try:
        async for chunk in remote_agent_chunks(
            messages,
            config,
            thread_id,
            user_context_preamble=user_context_preamble,
            invocation_id=invocation_id,
            directory=directory,
            workspace_id=workspace_id,
        ):
            yield chunk
    except NoUserMessage:
        yield "Error: No user message to send"
    except RemoteAgentUnavailable as exc:
        yield f"\n\n**Error:** {exc}"


async def remote_agent_chunks(
    messages: list[Message],
    config: ProviderConfig,
    thread_id: str,
    *,
    user_context_preamble: str | None,
    invocation_id: str | None,
    directory: RemoteAgentDirectory | None = None,
    workspace_id: str | None = None,
) -> AsyncGenerator[str | dict[str, Any], None]:
    """The turn's text and step chunks. Raises ``NoUserMessage``, and
    ``RemoteAgentUnavailable`` when no module serves the agent or its run
    fails before its answer is done; a failure after that (the run ending
    FAILED while the module saves it) is logged, the answer stands."""
    if directory is None:
        from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
            get_remote_agent_directory,
        )

        directory = get_remote_agent_directory()

    prompt = next((m.content for m in reversed(messages) if m.role == "user"), None)
    if not prompt:
        raise NoUserMessage()
    if user_context_preamble:
        prompt = f"{user_context_preamble.strip()}\n\n{prompt}"

    emitted = done = False
    final_replay: list[str] = []
    try:
        async for event in directory.stream(
            config.model,
            prompt,
            thread_id=thread_id,
            invocation_id=invocation_id,
            workspace_id=workspace_id,
        ):
            name, text = event.get("event", ""), str(event.get("data") or "")
            if name == "done" or text == "[DONE]":
                # Read on to the run's end: the module saves the run and frees
                # the conversation after its done event, and leaving the stream
                # early cancels the run. A next turn sent at once found it BUSY.
                done = True
                continue
            if done:
                continue
            if name == "message":
                if text.strip():
                    final_replay.append(text.strip())
                continue
            chunk = agent_event_chunk(name, text, chat_source=event.get("chat_source"))
            if chunk is not None:
                emitted = emitted or isinstance(chunk, str)
                yield chunk
    except RemoteAgentUnavailable as exc:
        if not done:
            raise
        logger.warning(
            "Remote agent %s failed after its answer was done: %s", config.model, exc.reason
        )

    # SDK-only agents may answer with ``message`` events alone.
    if not emitted and final_replay:
        yield "\n".join(final_replay)
