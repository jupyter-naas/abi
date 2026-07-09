"""Opencode harness adapter.

Wraps the existing :class:`desktop.opencode_client.OpencodeClient` (which
owns process spawning, HTTP/SSE plumbing and event filtering) and
translates its legacy dict events into the normalized harness events.
It deliberately does not reimplement any protocol logic.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import httpx

from ...opencode_client import OpencodeClient, OpencodeUnavailableError
from ..models import (
    DoneEvent,
    ErrorEvent,
    HarnessEvent,
    HarnessModel,
    HarnessProvider,
    ReasoningEvent,
    TextEvent,
    ToolEvent,
)
from ..port import HarnessPort, HarnessUnavailableError


class OpencodeHarnessAdapter(HarnessPort):
    """Adapter over a locally spawned ``opencode serve`` HTTP API."""

    def __init__(
        self,
        workspace_root: str,
        opencode_bin: str = "opencode",
        client: OpencodeClient | None = None,
    ):
        self._client = client or OpencodeClient(
            workdir=workspace_root, opencode_bin=opencode_bin
        )

    @property
    def client(self) -> OpencodeClient:
        """Underlying opencode client (exposed for legacy wiring)."""
        return self._client

    # -- lifecycle ------------------------------------------------------

    async def start(self) -> None:
        try:
            await asyncio.to_thread(self._client.start)
        except OpencodeUnavailableError as e:
            raise HarnessUnavailableError(str(e)) from e

    async def stop(self) -> None:
        await asyncio.to_thread(self._client.stop)

    async def restart(
        self, workspace_root: str | None = None, binary: str | None = None
    ) -> None:
        try:
            await asyncio.to_thread(self._client.restart, workspace_root, binary)
        except OpencodeUnavailableError as e:
            raise HarnessUnavailableError(str(e)) from e

    async def health(self) -> bool:
        return await asyncio.to_thread(self._client.is_running)

    # -- models / sessions ----------------------------------------------

    async def list_models(self) -> list[HarnessProvider]:
        raw_providers = await self._client.providers()
        providers: list[HarnessProvider] = []
        for provider in raw_providers:
            models = tuple(
                HarnessModel(id=str(m["id"]), name=str(m.get("name") or m["id"]))
                for m in provider.get("models", [])
                if m.get("id")
            )
            providers.append(
                HarnessProvider(
                    id=str(provider.get("id") or ""),
                    name=str(provider.get("name") or provider.get("id") or ""),
                    models=models,
                )
            )
        return providers

    async def create_session(
        self, title: str = "", workspace_root: str | None = None
    ) -> str:
        # opencode scopes sessions to the workdir the server was spawned
        # in; per-session workspace overrides are not supported.
        return await self._client.create_session(title=title or "New chat")

    async def delete_session(self, session_id: str) -> None:
        # OpencodeClient does not expose session deletion; issue the
        # DELETE ourselves against its endpoint. Reuse the client's own
        # http factory when present so injected transports are honored.
        try:
            base_url = self._client.base_url
        except OpencodeUnavailableError:
            return  # nothing running, nothing to delete
        make_client = getattr(self._client, "_client", None)
        client = (
            make_client(timeout=10.0)
            if make_client
            else httpx.AsyncClient(timeout=10.0)
        )
        async with client:
            await client.delete(f"{base_url}/session/{session_id}")

    async def abort(self, session_id: str) -> None:
        await self._client.abort(session_id)

    # -- prompting --------------------------------------------------------

    async def stream_prompt(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        done = False
        async for raw in self._client.stream_message(
            session_id, text, model=model, agent=agent
        ):
            event = _event_from_legacy(raw)
            if event is None:
                continue
            if isinstance(event, DoneEvent):
                done = True
            yield event
        if not done:
            # The legacy client can end early on transport errors; the
            # port contract guarantees a terminal DoneEvent.
            yield DoneEvent(text="")


def _event_from_legacy(raw: dict[str, Any]) -> HarnessEvent | None:
    kind = raw.get("type")
    if kind == "text":
        return TextEvent(
            text=str(raw.get("text") or ""), part_id=str(raw.get("part_id") or "")
        )
    if kind == "reasoning":
        return ReasoningEvent()
    if kind == "tool":
        return ToolEvent(
            call_id=str(raw.get("call_id") or ""),
            name=str(raw.get("tool") or "tool"),
            status=str(raw.get("status") or ""),
            title=str(raw.get("title") or ""),
        )
    if kind == "error":
        return ErrorEvent(message=str(raw.get("message") or ""))
    if kind == "complete":
        return DoneEvent(text=str(raw.get("text") or ""))
    return None
