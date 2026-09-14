"""Chat-style title from the first user prompt.

Chat names a new thread by clipping the first user line. Documents and Slides
reuse the same helper so an untitled office file gets the same kind of name
when the user sends the first real prompt.
"""

from __future__ import annotations

CHAT_TITLE_MAX_CHARS = 50


def conversation_title_from_prompt(message: str) -> str:
    """Same title Chat stores when a thread is created from the first send."""
    text = (message or "").strip()
    if not text:
        return ""
    if len(text) <= CHAT_TITLE_MAX_CHARS:
        return text
    return text[:CHAT_TITLE_MAX_CHARS] + "..."


def first_user_prompt(current: str, messages: list | None = None) -> str:
    """First real user line in the thread, else the current send.

    A follow-up on an already-open untitled file should still name it from
    the original brief, not from "continue".
    """
    for message in messages or []:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        text = str(content or "").strip()
        if str(role or "").strip() == "user" and text:
            return text
    return (current or "").strip()
