"""Normalized harness data model.

These types are the lingua franca between the desktop server and any AI
harness adapter. ``to_dict()`` produces exactly the wire shapes the web
UI already consumes over SSE (the legacy ``OpencodeClient`` dict events),
so the server can keep serializing with ``json.dumps(event.to_dict())``.

Wire shapes:

- ``{"type": "text", "text": str, "part_id": str}``   cumulative text part
- ``{"type": "reasoning"}``
- ``{"type": "tool", "tool", "status", "title", "call_id"[, "input", "output"]}``
- ``{"type": "error", "message": str}``
- ``{"type": "complete", "text": str}``                final assistant text
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union


@dataclass(frozen=True)
class HarnessModel:
    """A model exposed by a harness provider (id is provider-scoped)."""

    id: str
    name: str
    supports_tools: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "supports_tools": self.supports_tools,
        }


@dataclass(frozen=True)
class HarnessProvider:
    """A model provider (e.g. anthropic, openai) with its models."""

    id: str
    name: str
    models: tuple[HarnessModel, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "models": [model.to_dict() for model in self.models],
        }


@dataclass(frozen=True)
class TextEvent:
    """Cumulative assistant text for one output part (not a delta)."""

    text: str
    part_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text, "part_id": self.part_id}


@dataclass(frozen=True)
class ReasoningEvent:
    """The assistant is thinking (no content is exposed)."""

    def to_dict(self) -> dict[str, Any]:
        return {"type": "reasoning"}


@dataclass(frozen=True)
class ToolEvent:
    """Snapshot of one tool call. A call streams several snapshots keyed
    by ``call_id`` (e.g. pending -> running -> completed)."""

    call_id: str
    name: str
    status: str  # "pending" | "running" | "completed" | "error"
    title: str = ""
    input: dict[str, Any] | None = None
    output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "tool",
            "tool": self.name,
            "status": self.status,
            "title": self.title,
            "call_id": self.call_id,
        }
        if self.input is not None:
            payload["input"] = self.input
        if self.output is not None:
            payload["output"] = self.output
        return payload


@dataclass(frozen=True)
class ErrorEvent:
    """A recoverable error surfaced mid-stream."""

    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "error", "message": self.message}


@dataclass(frozen=True)
class DoneEvent:
    """Turn finished; ``text`` is the final assistant text (may be empty).

    Serializes as ``type: "complete"`` for wire compatibility with the
    legacy opencode event stream.
    """

    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": "complete", "text": self.text}


HarnessEvent = Union[TextEvent, ReasoningEvent, ToolEvent, ErrorEvent, DoneEvent]
