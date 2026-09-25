import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from naas_abi_sdk.module import (
    BaseModule,
    EngineProxy,
    ModuleConfiguration,
    ModuleDependencies,
    run_module,
)


def test_dependencies_deny_undeclared_access_and_support_engine_aliases():
    client = MagicMock()
    engine = EngineProxy(client, ModuleDependencies(services=("kv", "events")))
    assert engine.services.kv._client is client.keyvalue
    assert engine.rpc.kv is client.keyvalue
    assert engine.services.events._client is client.event
    with pytest.raises(ValueError, match="did not declare"):
        _ = engine.services.secret
    with pytest.raises(ValueError, match="Unknown remote"):
        EngineProxy(client, ModuleDependencies(services=("typo",)))
    with pytest.raises(ValueError, match="discovery"):
        EngineProxy(client, ModuleDependencies(modules=("other",)))


@pytest.mark.parametrize("failure", [None, "load", "initialized", "run"])
def test_lifecycle_order_and_cleanup_on_failure(monkeypatch, failure):
    order = []
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)

    class ABIModule(BaseModule):
        @dataclass
        class Configuration(ModuleConfiguration):
            value: str = "configured"

        dependencies = ModuleDependencies(services=("object_storage",))

        def on_load(self):
            order.append("load")
            if failure == "load":
                raise RuntimeError("load")

        async def on_initialized(self):
            order.append("initialized")
            if failure == "initialized":
                raise RuntimeError("initialized")

        async def run(self):
            order.append("run")
            assert self.engine.services.object_storage._client is client.object_storage
            if failure == "run":
                raise RuntimeError("run")
            return self.configuration.value

        async def on_unloaded(self):
            order.append("unloaded")

    task = run_module(ABIModule, url="nats://unused", token="issued")
    if failure:
        with pytest.raises(RuntimeError, match=failure):
            asyncio.run(task)
    else:
        assert asyncio.run(task) == "configured"
    expected = ["load", "initialized", "run"]
    assert order == (
        expected[: expected.index(failure) + 1] if failure else expected
    ) + ["unloaded"]
    client.__aexit__.assert_awaited_once()


def test_current_module_is_task_scoped_and_expired_after_unload(monkeypatch):
    import contextvars

    from naas_abi_sdk import current_module

    def client_factory(*args, **kwargs):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        return client

    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client_factory)
    with pytest.raises(RuntimeError, match="No active module"):
        current_module()
    captures = []

    class Module(BaseModule):
        async def on_load(self):
            assert current_module() is self

        async def run(self):
            await asyncio.sleep(0)
            assert current_module() is self
            assert await asyncio.to_thread(current_module) is self
            captures.append(contextvars.copy_context())
            return self

        def on_unloaded(self):
            assert current_module() is self

    async def scenario():
        return await asyncio.gather(
            *(run_module(Module, url="unused", token="issued") for _ in range(2))
        )

    first, second = asyncio.run(scenario())
    assert first is not second
    assert first.engine is not second.engine
    for context in captures:
        with pytest.raises(RuntimeError, match="No active module"):
            context.run(current_module)
    with pytest.raises(RuntimeError, match="No active module"):
        current_module()


def test_current_module_cleanup_on_cancellation(monkeypatch):
    from naas_abi_sdk import current_module

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)
    unloaded = []

    class Module(BaseModule):
        async def run(self):
            assert current_module() is self
            raise asyncio.CancelledError()

        def on_unloaded(self):
            unloaded.append(current_module() is self)

    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            await run_module(Module, url="unused", token="issued")
        with pytest.raises(RuntimeError, match="No active module"):
            current_module()

    asyncio.run(scenario())
    assert unloaded == [True]
    client.__aexit__.assert_awaited_once()
