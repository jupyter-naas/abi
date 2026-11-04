from __future__ import annotations

import asyncio

import pytest
from naas_abi_marketplace.applications.ten_agent.adapters.secondary.ten_agent__secondary_adapter__AbiInProcess import (
    AbiInProcessAgentStream,
)
from naas_abi_marketplace.applications.ten_agent.domain.ports import AgentMessage

provider_runtime = pytest.importorskip(
    "naas_abi.apps.nexus.apps.api.app.services.provider_runtime"
)


def test_streams_raw_chunks_from_the_inprocess_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict = {}

    async def fake(messages, config, thread_id, *, user_context_preamble):
        seen.update(
            roles=[m.role for m in messages],
            model=config.model,
            thread_id=thread_id,
            preamble=user_context_preamble,
        )
        yield {"event": "tool_usage", "tool": "x"}
        yield "Hi."

    monkeypatch.setattr(provider_runtime, "stream_with_abi_inprocess", fake)

    async def run() -> list:
        return [
            c
            async for c in AbiInProcessAgentStream().stream(
                "AbiAgent",
                [AgentMessage("system", "s"), AgentMessage("user", "u")],
                "voice-u1-call-1",
                "style",
            )
        ]

    assert asyncio.run(run()) == [{"event": "tool_usage", "tool": "x"}, "Hi."]
    assert seen == {
        "roles": ["system", "user"],
        "model": "AbiAgent",
        "thread_id": "voice-u1-call-1",
        "preamble": "style",
    }
