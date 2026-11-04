"""Ports for real-time voice calls over ABI agents.

Two boundaries, both independent of TEN:

- ``VoiceEnginePort``: the engine that hears and speaks (TEN Agent today,
  OpenAI Realtime next). It turns one call into a session a client can join.
- ``AgentStreamPort``: the ABI agent the engine asks for answers. The voice
  gateway reads raw chunks from it and decides what may be spoken.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class AgentMessage:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass(frozen=True)
class VoiceSessionRequest:
    """One call. ``gateway_base_url`` is where the engine reaches ABI."""

    call_id: str
    agent: str
    gateway_base_url: str


@dataclass(frozen=True)
class VoiceSession:
    """What a client needs to join the call, and what the engine needs to run it.

    ``env`` carries credentials for the engine process and is never rendered
    into ``engine_config``, logged, or returned to a browser.
    """

    engine: str
    transport: Literal["websocket", "webrtc"]
    url: str
    call_id: str
    engine_config: dict[str, Any]
    env: dict[str, str] = field(default_factory=dict, repr=False)


class VoiceEnginePort(ABC):
    name: str

    @abstractmethod
    def open_session(
        self, request: VoiceSessionRequest, gateway_token: str
    ) -> VoiceSession:
        """Prepare a session. ``gateway_token`` authenticates the engine to ABI."""


class AgentStreamPort(ABC):
    @abstractmethod
    def stream(
        self,
        agent: str,
        messages: list[AgentMessage],
        thread_id: str,
        preamble: str | None,
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Text deltas (``str``) and agent events (``dict`` with an ``event`` key)."""
