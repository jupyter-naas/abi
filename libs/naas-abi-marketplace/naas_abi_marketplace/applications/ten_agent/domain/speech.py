"""Speech-safe rendering of an ABI agent stream for a voice engine.

A voice engine (TEN Agent's ``openai_llm2_python``, or a Realtime model calling
ABI as a tool) sends every token it receives to text-to-speech. The rendering
the gateway gives Continue is markdown with tool banners, fenced tool output
and a hidden chat-id comment, and a TTS reads all of it aloud. This module turns
agent chunks into sentences a voice can say.

No FastAPI and no agent imports: the adapter feeds it chunks, so it is tested
with plain lists.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Any

DEFAULT_FILLER = "One moment, let me check."

VOICE_STYLE = (
    "You are speaking on a live voice call. Answer in one to three short spoken "
    "sentences. Do not use markdown, lists, tables, code or URLs."
)

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL_RE = re.compile(r"https?://\S+")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_LINE_MARKER_RE = re.compile(r"^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)")
_TABLE_RULE_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
_EMPHASIS_RE = re.compile(r"\*\*|__|`|~~|(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)")
_SYMBOLS_RE = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")


def to_speech(segment: str) -> str:
    """One complete line or sentence of agent markdown, as words to say."""
    text = _HTML_COMMENT_RE.sub("", segment)
    if _TABLE_RULE_RE.match(text):
        return ""
    text = _LINE_MARKER_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _URL_RE.sub("", text)
    text = _EMPHASIS_RE.sub("", text)
    text = _SYMBOLS_RE.sub("", text)
    text = text.strip(" |").replace(" | ", ", ")
    return " ".join(text.split())


class SpeechStream:
    """Buffers streamed agent text and releases it one speakable sentence at a time.

    Sentences, not tokens, because markdown markers split across deltas (``*``
    then ``*bold**``) and fenced blocks are only recognisable once their line is
    complete. A voice engine segments by sentence before TTS anyway, so holding
    text until the sentence ends costs nothing audible.
    """

    def __init__(self, filler: str | None = DEFAULT_FILLER) -> None:
        self._filler = filler
        self._buffer = ""
        self._in_fence = False
        self._spoken = False

    def feed(self, chunk: str | dict[str, Any]) -> list[str]:
        if isinstance(chunk, dict):
            return self._on_event(chunk)
        self._buffer += chunk
        out: list[str] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            out.extend(self._line(line))
        out.extend(self._line_partial())
        return out

    def flush(self) -> list[str]:
        line, self._buffer = self._buffer, ""
        return self._line(line)

    def _on_event(self, event: dict[str, Any]) -> list[str]:
        # The tool runs server-side, often for seconds. Say something first,
        # unless the agent already did.
        if event.get("event") == "tool_usage" and self._filler and not self._spoken:
            self._spoken = True
            return [self._filler]
        return []

    def _line(self, line: str) -> list[str]:
        if line.lstrip().startswith("```"):
            self._in_fence = not self._in_fence
            return []
        if self._in_fence:
            return []
        return self._say(_SENTENCE_END_RE.split(line))

    def _line_partial(self) -> list[str]:
        """Release finished sentences of the line still being streamed."""
        if self._in_fence or self._buffer.lstrip().startswith("`"):
            return []
        parts = _SENTENCE_END_RE.split(self._buffer)
        self._buffer = parts.pop()
        return self._say(parts)

    def _say(self, parts: Iterable[str]) -> list[str]:
        spoken = [s for s in (to_speech(p) for p in parts) if s]
        if spoken:
            self._spoken = True
        return spoken


async def speakable(
    chunks: AsyncIterable[str | dict[str, Any]],
    filler: str | None = DEFAULT_FILLER,
) -> AsyncIterator[str]:
    """Agent chunks in, speakable deltas out (each ends with a space)."""
    stream = SpeechStream(filler)
    async for chunk in chunks:
        for sentence in stream.feed(chunk):
            yield f"{sentence} "
    for sentence in stream.flush():
        yield f"{sentence} "


def voice_thread_id(session: str | None, user_id: str) -> str:
    """Checkpointer thread for a voice call.

    The ABI agent receives only the latest user message and keeps the rest of
    the conversation in its checkpointer, so every turn of one call must land on
    the same thread. A voice engine cannot round-trip the hidden chat marker the
    Continue path uses; it sends a per-call session id instead. The id is scoped
    to the authenticated user, so a guessed or reused session id never reaches
    another user's thread. Without one, the turn gets a fresh thread.
    """
    if session and _SESSION_RE.match(session):
        return f"voice-{user_id}-{session}"
    return f"voice-{user_id}-{uuid.uuid4().hex}"


def voice_preamble(profile: str | None) -> str:
    return f"{VOICE_STYLE}\n\n{profile}" if profile else VOICE_STYLE
