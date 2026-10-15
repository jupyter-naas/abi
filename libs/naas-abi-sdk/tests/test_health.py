import asyncio
import http.client
from unittest.mock import AsyncMock, MagicMock

import pytest

from naas_abi_sdk.health import HealthServer
from naas_abi_sdk.module import BaseModule, run_module


def _get(port: int, path: str) -> tuple[int, str]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read().decode().strip()
    finally:
        connection.close()


def test_liveness_stays_up_and_readiness_follows_status():
    async def scenario():
        state = {"status": "STARTING"}
        server = HealthServer(lambda: state["status"], "127.0.0.1", 0)
        await server.start()
        try:
            assert await asyncio.to_thread(_get, server.port, "/health") == (200, "ok")
            assert await asyncio.to_thread(_get, server.port, "/ready") == (
                503,
                "STARTING",
            )
            for status in ("STAGED", "DEGRADED", "DRAINING", "UNAVAILABLE"):
                state["status"] = status
                assert await asyncio.to_thread(_get, server.port, "/health") == (
                    200,
                    "ok",
                )
                assert await asyncio.to_thread(_get, server.port, "/ready") == (
                    503,
                    status,
                )
            state["status"] = "READY"
            assert await asyncio.to_thread(_get, server.port, "/ready") == (
                200,
                "READY",
            )
            state["status"] = "DISABLED"
            assert await asyncio.to_thread(_get, server.port, "/ready") == (
                200,
                "DISABLED",
            )
            assert (await asyncio.to_thread(_get, server.port, "/nope"))[0] == 404
            assert await asyncio.to_thread(_get, server.port, "/ready?watch=1") == (
                200,
                "DISABLED",
            )
        finally:
            await server.close()

    asyncio.run(scenario())


def test_module_serves_the_probe_only_while_it_runs(monkeypatch):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)
    seen = {}

    class Module(BaseModule):
        async def run(self):
            seen["port"] = self.health_port
            assert await asyncio.to_thread(_get, self.health_port, "/health") == (
                200,
                "ok",
            )
            assert await asyncio.to_thread(_get, self.health_port, "/ready") == (
                200,
                "DISABLED",
            )

    asyncio.run(run_module(Module, url="nats://unused", token="issued", health_port=0))
    with pytest.raises(OSError):
        _get(seen["port"], "/health")


def test_an_unset_health_port_opens_nothing(monkeypatch):
    monkeypatch.delenv("ABI_HEALTH_PORT", raising=False)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)

    class Module(BaseModule):
        async def run(self):
            assert self.health_port is None

    asyncio.run(run_module(Module, url="nats://unused", token="issued"))


def test_health_port_must_be_a_tcp_port():
    with pytest.raises(ValueError, match="Health port"):
        asyncio.run(
            run_module(BaseModule, url="nats://unused", token="issued", health_port=-1)
        )
