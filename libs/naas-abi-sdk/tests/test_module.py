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
    assert engine.services.kv is client.keyvalue
    assert engine.services.events is client.event
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
            assert self.engine.services.object_storage is client.object_storage
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
