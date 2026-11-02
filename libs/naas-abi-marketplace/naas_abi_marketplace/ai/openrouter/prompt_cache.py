"""Anthropic prompt caching through OpenRouter.

Anthropic only caches a prompt prefix that ends on a ``cache_control``
breakpoint. Its prefix order is tools, then system, then messages, so one
breakpoint on the system prompt caches the tool list with it; a second one on
the last user message caches the conversation so far, which the next model
call of a tool loop reads back. OpenRouter forwards ``cache_control`` from
OpenAI-style content parts to Anthropic.

Only Anthropic models get breakpoints: other providers behind OpenRouter
either cache on their own or reject the field.
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

CACHE_CONTROL = {"type": "ephemeral"}


def _with_breakpoint(content: Any) -> Any:
    """``content`` with a breakpoint on its last text part, or unchanged."""
    if isinstance(content, str):
        if not content.strip():
            return content
        return [{"type": "text", "text": content, "cache_control": CACHE_CONTROL}]
    if isinstance(content, list) and content:
        last = content[-1]
        if isinstance(last, dict) and last.get("type") == "text" and last.get("text"):
            return [*content[:-1], {**last, "cache_control": CACHE_CONTROL}]
    return content


def add_cache_breakpoints(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark the first system message and the last user message (OpenAI format)."""
    marked = [dict(message) for message in messages]
    system = next((m for m in marked if m.get("role") in ("system", "developer")), None)
    if system is not None:
        system["content"] = _with_breakpoint(system.get("content"))
    user = next((m for m in reversed(marked) if m.get("role") == "user"), None)
    if user is not None:
        user["content"] = _with_breakpoint(user.get("content"))
    return marked


def is_anthropic_model(model_id: str | None) -> bool:
    return (model_id or "").lower().startswith("anthropic/")


class OpenRouterChatOpenAI(ChatOpenAI):
    """``ChatOpenAI`` on OpenRouter that adds Anthropic cache breakpoints."""

    def _get_request_payload(self, input_: Any, *, stop=None, **kwargs: Any) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = payload.get("messages")
        if is_anthropic_model(payload.get("model") or self.model_name) and messages:
            payload["messages"] = add_cache_breakpoints(messages)
        return payload
