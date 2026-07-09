"""Port contract tests: abstractness and a minimal conforming adapter."""

from typing import AsyncIterator

import pytest

from desktop.harness.models import DoneEvent, HarnessEvent, HarnessProvider, TextEvent
from desktop.harness.port import HarnessPort


def test_port_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        HarnessPort()  # type: ignore[abstract]


class _MinimalAdapter(HarnessPort):
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def restart(
        self, workspace_root: str | None = None, binary: str | None = None
    ) -> None:
        pass

    async def health(self) -> bool:
        return True

    async def list_models(self) -> list[HarnessProvider]:
        return []

    async def create_session(
        self, title: str = "", workspace_root: str | None = None
    ) -> str:
        return "s1"

    async def delete_session(self, session_id: str) -> None:
        pass

    async def abort(self, session_id: str) -> None:
        pass

    async def stream_prompt(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        yield TextEvent(text="hi", part_id="p1")
        yield DoneEvent(text="hi")


@pytest.mark.asyncio
async def test_minimal_adapter_satisfies_contract() -> None:
    adapter = _MinimalAdapter()
    await adapter.start()
    assert await adapter.health() is True
    session_id = await adapter.create_session("t")

    events = [event async for event in adapter.stream_prompt(session_id, "hello")]
    assert isinstance(events[-1], DoneEvent)
    assert events[0].to_dict()["type"] == "text"

    await adapter.delete_session(session_id)
    await adapter.stop()
