from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.discovery import (
    DiscoveryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.contracts import (
    RESEARCHER,
    RemoteAgentDirectoryContract,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import RemoteAgentUnavailable
from naas_abi_sdk.discovery import AgentDescriptor, ModuleInstance
from naas_abi_sdk.transport import RPCError

INVOKE = ("agent.invoke.v1",)


def _instance(module_id, instance_id, status="READY", agents=(), contract_major=1):
    return ModuleInstance(
        module_id, instance_id, "1.0.0", contract_major, status, 0.0, tuple(agents)
    )


RESEARCHER_DESCRIPTOR = AgentDescriptor(RESEARCHER.name, RESEARCHER.description, 1, INVOKE)
INSTANCES = [
    _instance("acme.research", "i-1", agents=[RESEARCHER_DESCRIPTOR]),
    _instance("acme.research", "i-2", agents=[RESEARCHER_DESCRIPTOR]),  # replica
    _instance(
        "acme.draining", "i-3", status="DRAINING", agents=[AgentDescriptor("Gone", "", 1, INVOKE)]
    ),
    _instance("acme.tools", "i-4", agents=[AgentDescriptor("NoInvoke", "", 1, ())]),
    _instance("acme.v2", "i-5", agents=[AgentDescriptor("Future", "", 2, INVOKE)]),
]


class _Discovery:
    """DiscoveryClient.list_modules, paginated two instances at a time."""

    async def list_modules(self, *, limit=100, after_instance_id=""):
        start = (
            0
            if not after_instance_id
            else next(i for i, x in enumerate(INSTANCES) if x.instance_id == after_instance_id) + 1
        )
        page = INSTANCES[start : start + 2]
        more = start + 2 < len(INSTANCES)
        return tuple(page), page[-1].instance_id if more else ""


class _Handle:
    def __init__(self, proxy, prompt):
        self.proxy, self.prompt, self.cancelled = proxy, prompt, False

    async def events(self, *, timeout=None):
        if self.prompt == "boom":
            raise RPCError("AGENT_FAILED", "handler raised")
        yield {"event": "ai_message", "data": f"fact: {self.prompt}"}
        if self.prompt == "slow":
            await asyncio.sleep(10)
        yield {"event": "done", "data": "[DONE]"}

    async def cancel(self):
        self.cancelled = True


class _Proxy:
    handles: list[_Handle] = []

    def __init__(self, thread_id=""):
        self.thread_id = thread_id

    def duplicate(self, agent_shared_state=None):
        return _Proxy(agent_shared_state.thread_id)

    async def submit(self, prompt, *, invocation_id=None, stream=False):
        assert stream
        handle = _Handle(self, prompt)
        _Proxy.handles.append(handle)
        return handle


async def _open_agent(client, module_id, name):
    instances = [i for i in INSTANCES if i.module_id == module_id and i.status == "READY"]
    if not any(a.name == name for i in instances for a in i.agents):
        raise RPCError("AGENT_NOT_FOUND", name)
    return _Proxy()


@pytest.fixture
def directory():
    _Proxy.handles = []
    return DiscoveryRemoteAgentDirectory(_Discovery, open_agent=_open_agent)


class TestDiscoveryRemoteAgentDirectory(RemoteAgentDirectoryContract):
    pass


def test_runs_on_the_conversation_thread(directory):
    async def run():
        return [e async for e in directory.stream(RESEARCHER.key, "q", thread_id="conv-7")]

    asyncio.run(run())

    assert _Proxy.handles[0].proxy.thread_id == "conv-7"


def test_failed_run_is_unavailable_with_its_code(directory):
    async def run():
        return [e async for e in directory.stream(RESEARCHER.key, "boom", thread_id="c")]

    with pytest.raises(RemoteAgentUnavailable, match="AGENT_FAILED"):
        asyncio.run(run())


def test_oversized_prompt_is_rejected_before_submitting(directory):
    async def run():
        return [
            e async for e in directory.stream(RESEARCHER.key, "x" * (64 * 1024 + 1), thread_id="c")
        ]

    with pytest.raises(RemoteAgentUnavailable, match="64 KiB"):
        asyncio.run(run())
    assert _Proxy.handles == []


def test_abandoned_stream_cancels_the_remote_run(directory):
    async def run():
        stream = directory.stream(RESEARCHER.key, "slow", thread_id="c")
        assert (await anext(stream))["data"] == "fact: slow"
        await stream.aclose()  # client disconnected

    asyncio.run(run())

    assert _Proxy.handles[0].cancelled


def test_one_discovery_client_per_event_loop():
    made = []

    def factory():
        made.append(object())
        return _Discovery()

    directory = DiscoveryRemoteAgentDirectory(factory, open_agent=_open_agent)

    async def twice():
        await directory.list_agents()
        await directory.list_agents()

    asyncio.run(twice())
    asyncio.run(twice())

    assert len(made) == 2
