"""Cancelling a call to a tool an SDK module serves, on a real broker
(docs/adr/20261026_tool-call-cancellation.md).

The engine runs a module's tool for an agent; when the agent's call is cancelled, the
engine tells the module instance it chose, and the module stops the handler: an async
handler at its next await (its ``finally`` runs), a synchronous one through
``call.cancellation``. A call between two modules does the same.
"""

import asyncio
import threading

import pytest

# The engine, the broker and the module process are those of the remote tools suite;
# its fixtures are imported by name (F811: a test's argument names the imported one).
# ruff: noqa: F811
from naas_abi_core.engine.Engine_remote_tools_nats_integration_test import (  # noqa: F401
    MODULE,
    PASSWORDS,
    PROJECT,
    SECRET,
    USER,
    RunningModule,
    broker,
    engine_dir,
    published,
    serving,
    wait_for,
)

ASYNC_TOOL = f"{MODULE}/wait_async@1"
SYNC_TOOL = f"{MODULE}/wait_sync@1"

PROBE = {"started": threading.Event(), "cleaned": threading.Event(), "told": None}


def build_module():
    from naas_abi_sdk import BaseModule, ToolDescriptor

    async def wait_async(arguments):
        PROBE["started"].set()
        try:
            await asyncio.sleep(60)
        finally:
            PROBE["cleaned"].set()

    def wait_sync(arguments, call):
        PROBE["started"].set()
        PROBE["told"] = call.cancellation.wait(60)
        PROBE["cleaned"].set()
        return "stopped"

    class Crm(BaseModule):
        tools = (
            ToolDescriptor(
                "wait_async", "Wait without end, as a coroutine, until cancelled."
            ),
            ToolDescriptor(
                "wait_sync", "Wait without end, on a thread, until cancelled."
            ),
        )

        def on_initialized(self):
            self.expose_tool("wait_async", wait_async)
            self.expose_tool("wait_sync", wait_sync)

        async def run(self):
            await asyncio.Event().wait()

    Crm.module_id = MODULE
    return Crm


@pytest.fixture
def crm(serving, broker):
    PROBE["started"].clear()
    PROBE["cleaned"].clear()
    PROBE["told"] = None
    running = RunningModule(broker, build_module()).start()
    wait_for(lambda: {ASYNC_TOOL, SYNC_TOOL} <= published(serving))
    yield running
    running.stop()


@pytest.mark.parametrize("tool_id", [ASYNC_TOOL, SYNC_TOOL])
def test_an_agent_that_gives_up_cancels_the_modules_handler(serving, crm, tool_id):
    built = serving.services.tool_registry.resolve(tool_id, USER)

    async def scenario():
        running = asyncio.ensure_future(built.ainvoke({}))
        assert await asyncio.to_thread(PROBE["started"].wait, 15)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        return await asyncio.to_thread(PROBE["cleaned"].wait, 15)

    assert asyncio.run(scenario()) is True
    if tool_id == SYNC_TOOL:
        assert PROBE["told"] is True


def test_a_module_calling_a_module_tool_cancels_it_the_same_way(serving, crm, broker):
    from naas_abi_core.engine.nats_auth import ServiceTokenSource
    from naas_abi_core.engine.nats_test_server import login
    from naas_abi_sdk.discovery import DiscoveryClient, ModuleProxy
    from naas_abi_sdk.transport import Transport

    async def scenario():
        # The module's default hook admits the engine's own processes only: call
        # as one of them (the engine's service identity).
        transport = Transport(
            login(broker, "module", PASSWORDS["module"]),
            ServiceTokenSource("engine", SECRET),
            timeout=30,
        )
        try:
            proxy = ModuleProxy(DiscoveryClient(transport, PROJECT), MODULE)
            running = asyncio.ensure_future(proxy.call_tool("wait_async", {}))
            assert await asyncio.to_thread(PROBE["started"].wait, 15)
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
            return await asyncio.to_thread(PROBE["cleaned"].wait, 15)
        finally:
            await transport.close()

    assert asyncio.run(scenario()) is True


def test_only_the_identity_that_started_a_call_can_cancel_it(
    serving, crm, broker, monkeypatch
):
    """The call's real id, from another module's token: nothing is stopped. From the
    caller's own identity (the engine's) on a new connection: it is."""
    from naas_abi_core.engine.nats_auth import ServiceTokenSource, module_key
    from naas_abi_core.engine.nats_test_server import login
    from naas_abi_sdk import tools
    from naas_abi_sdk.service_token import ModuleToken
    from naas_abi_sdk.tools import ModuleToolClient, tool_subject
    from naas_abi_sdk.transport import Transport

    monkeypatch.setattr(tools, "new_call_id", lambda: "known-call-id-1")
    built = serving.services.tool_registry.resolve(ASYNC_TOOL, USER)
    instances: list[str] = []
    original = ModuleToolClient.invoke

    async def noting(self, request, **kwargs):
        instances.append(self.instance_id)
        return await original(self, request, **kwargs)

    monkeypatch.setattr(ModuleToolClient, "invoke", noting)

    async def cancel_as(token):
        transport = Transport(
            login(broker, "module", PASSWORDS["module"]), token, timeout=10
        )
        try:
            client = ModuleToolClient(
                transport,
                tool_subject(PROJECT, instances[0], "wait_async"),
                instances[0],
            )
            return await client.cancel("known-call-id-1")
        finally:
            await transport.close()

    async def scenario():
        running = asyncio.ensure_future(built.ainvoke({}))
        assert await asyncio.to_thread(PROBE["started"].wait, 15)
        stranger = await cancel_as(
            ModuleToken("stranger", module_key(SECRET, "stranger"))
        )
        await asyncio.sleep(0.3)
        untouched = not PROBE["cleaned"].is_set() and not running.done()
        owner = await cancel_as(ServiceTokenSource("engine", SECRET))
        stopped = await asyncio.to_thread(PROBE["cleaned"].wait, 15)
        # The module answered the call itself; its agent reads the code as text.
        reported = await asyncio.wait_for(running, 15)
        assert str(reported).startswith("CANCELLED")
        return stranger, untouched, owner, stopped

    stranger, untouched, owner, stopped = asyncio.run(scenario())
    assert (stranger, untouched, owner, stopped) == (False, True, True, True)
