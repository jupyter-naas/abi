"""Harness port: the interface every AI-harness adapter implements.

Mirrors the ports-and-adapters pattern of ``naas_abi_core`` services but
is implemented standalone (this package must not import the engine).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from .models import HarnessEvent, HarnessProvider


class HarnessError(Exception):
    """Base error for harness operations."""


class HarnessUnavailableError(HarnessError):
    """The harness binary/server is missing or failed to start."""


class HarnessPort(ABC):
    """Driver-side port for a local AI coding harness.

    Contract notes:

    - ``start`` is idempotent and raises ``HarnessUnavailableError`` when
      the harness cannot be spawned or attached.
    - ``stream_prompt`` yields normalized :mod:`.models` events and always
      terminates with a ``DoneEvent`` (possibly preceded by ``ErrorEvent``).
    - ``model`` strings follow the desktop convention ``provider/model_id``.
    - Adapters that genuinely cannot support an operation raise
      ``NotImplementedError`` with a clear message.
    """

    @abstractmethod
    async def start(self) -> None:
        """Spawn or attach to the harness (idempotent)."""

    @abstractmethod
    async def stop(self) -> None:
        """Tear down any spawned processes."""

    @abstractmethod
    async def restart(
        self, workspace_root: str | None = None, binary: str | None = None
    ) -> None:
        """Stop, optionally repoint workspace/binary, and start again."""

    @abstractmethod
    async def health(self) -> bool:
        """True when the harness is running or ready to be started."""

    @abstractmethod
    async def list_models(self) -> list[HarnessProvider]:
        """Providers and models the harness can route prompts to."""

    @abstractmethod
    async def create_session(
        self, title: str = "", workspace_root: str | None = None
    ) -> str:
        """Create a conversation session and return its id."""

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Dispose of a session and its resources."""

    @abstractmethod
    async def abort(self, session_id: str) -> None:
        """Abort the in-flight prompt of a session (no-op when idle)."""

    @abstractmethod
    def stream_prompt(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        """Send a prompt and yield normalized events until the turn ends."""
