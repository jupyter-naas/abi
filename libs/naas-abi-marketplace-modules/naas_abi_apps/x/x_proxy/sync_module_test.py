"""The app and the dataset sync over ``SyncModule``, as the module runs them.

The engine's services are async (the SDK's, over NATS); the X bodies are
synchronous and reach them through ``SyncModule`` from its own threads. Here
the services are async wrappers of the fakes, the sync runs with
``SyncModule.call`` and the app is called through httpx's ASGI transport on the
same loop: a blocking call made on the loop itself would raise.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import httpx
from naas_abi_apps.x.services import SyncModule
from naas_abi_apps.x.x_proxy.app import create_app
from naas_abi_apps.x.x_proxy.dataset.envelope_paths import ENVELOPE_PREFIX
from naas_abi_apps.x.x_proxy.dataset.sync import sync_envelope_paths
from naas_abi_apps.x.x_proxy.testing import FakeDataset, MemoryObjectStorage

ROOT = "/app-remote/abi_gk_1_secret/applications.x/x_proxy"


class Async:
    """A blocking fake seen as an SDK service: every method a coroutine."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        async def call(*args: Any, **kwargs: Any) -> Any:
            return attr(*args, **kwargs)

        return call


def _envelope() -> bytes:
    return json.dumps(
        {
            "query": "drones",
            "started_at": "2026-09-01T12:00:00+00:00",
            "ended_at": "2026-09-01T12:01:00+00:00",
            "results": {
                "data": [
                    {
                        "id": "100",
                        "author_id": "42",
                        "text": "a drone",
                        "created_at": "2026-09-01T11:59:00+00:00",
                    }
                ],
                "includes": {"users": [{"id": "42", "username": "pilot"}]},
            },
        }
    ).encode()


def test_sync_then_serve_through_sync_module() -> None:
    dataset = FakeDataset()
    storage = MemoryObjectStorage()
    storage.put_object(ENVELOPE_PREFIX, "2026-09-01T12_00_00Z_drones.json", _envelope())
    configuration = SimpleNamespace(
        app=SimpleNamespace(
            dataset=SimpleNamespace(sync_enabled=True, read_enabled=True)
        )
    )
    module = SimpleNamespace(
        configuration=configuration,
        engine=SimpleNamespace(
            services=SimpleNamespace(
                dataset=Async(dataset), object_storage=Async(storage)
            )
        ),
    )

    async def scenario() -> tuple[dict, httpx.Response, httpx.Response]:
        module.sync = SyncModule(module, asyncio.get_running_loop())
        summary = await module.sync.call(
            sync_envelope_paths,
            module.sync,
            [f"{ENVELOPE_PREFIX}/2026-09-01T12_00_00Z_drones.json"],
        )
        transport = httpx.ASGITransport(app=create_app(module), root_path=ROOT)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://module"
        ) as client:
            post = await client.get(f"{ROOT}/dataset/posts/100.json")
            users = await client.get(f"{ROOT}/dataset/users/search.json?q=pil")
        return summary, post, users

    summary, post, users = asyncio.run(scenario())
    assert summary["ingested_envelopes"] == 1
    assert post.status_code == 200
    assert post.json()["post"]["username"] == "pilot"
    assert users.json()["users"][0]["username"] == "pilot"


def test_a_blocking_call_on_the_loop_raises_instead_of_hanging() -> None:
    dataset = FakeDataset()
    module = SimpleNamespace(
        configuration=SimpleNamespace(),
        engine=SimpleNamespace(services=SimpleNamespace(dataset=Async(dataset))),
    )

    async def scenario() -> None:
        sync = SyncModule(module, asyncio.get_running_loop())
        sync.engine.services.dataset.list()

    try:
        asyncio.run(scenario())
    except RuntimeError as exc:
        assert "SyncModule.call" in str(exc)
    else:
        raise AssertionError("a blocking call on the loop must raise")
