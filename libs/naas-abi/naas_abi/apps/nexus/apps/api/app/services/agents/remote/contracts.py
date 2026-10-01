"""Generic adapter tests for RemoteAgentDirectory. An adapter's test module subclasses
the contract as ``Test...`` and provides a ``directory`` fixture publishing one agent,
``acme.research/Researcher``, that answers ``"fact: " + prompt`` and records thread ids."""

from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    RemoteAgent,
    RemoteAgentUnavailable,
)

RESEARCHER = RemoteAgent("acme.research", "Researcher", "Answers research questions.")


async def _collect(stream) -> list[dict[str, str]]:
    return [event async for event in stream]


class RemoteAgentDirectoryContract:
    def test_lists_the_published_agent_once(self, directory):
        assert asyncio.run(directory.list_agents()) == [RESEARCHER]

    def test_stream_yields_the_answer_then_done(self, directory):
        events = asyncio.run(
            _collect(directory.stream(RESEARCHER.key, "jetstream", thread_id="c-1"))
        )

        assert events[-1]["event"] == "done"
        assert "fact: jetstream" in "".join(e["data"] for e in events[:-1])

    def test_unknown_agent_is_unavailable(self, directory):
        with pytest.raises(RemoteAgentUnavailable):
            asyncio.run(_collect(directory.stream("acme.research/Nobody", "q", thread_id="c-1")))
