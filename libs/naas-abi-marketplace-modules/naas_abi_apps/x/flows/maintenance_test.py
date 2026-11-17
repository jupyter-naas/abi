"""The ``build_app`` and ``compact_dataset`` job bodies: off the loop, on ``module.sync``."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest
from naas_abi_apps.x.flows import maintenance
from naas_abi_apps.x.flows.conftest import x_module
from naas_abi_apps.x.x_proxy.dataset import maintenance as dataset_maintenance
from naas_abi_apps.x.x_proxy.dataset import media_worker


class Calls(list):
    """What the stubbed app, media worker and dataset did, and from which thread."""

    run: Any


@pytest.fixture
def calls(monkeypatch):
    calls = Calls()
    loop_thread: list[int] = []

    def off_loop() -> bool:
        return threading.get_ident() != loop_thread[0]

    def publish(module, **kwargs):
        calls.append(("publish", module, off_loop()))
        return {"queries": 1}

    def media(module, *, limit):
        calls.append(("media", (module, limit), off_loop()))
        return {"processed": 0}

    def compact(dataset):
        calls.append(("compact", dataset, off_loop()))
        return {"tables": ["posts_v1"]}

    monkeypatch.setattr(maintenance, "publish_x_app", publish)
    monkeypatch.setattr(media_worker, "process_pending_media_batch", media)
    monkeypatch.setattr(dataset_maintenance, "compact_x_datasets", compact)

    def run(coro):
        async def main():
            loop_thread.append(threading.get_ident())
            return await coro

        return asyncio.run(main())

    calls.run = run
    return calls


def test_build_app_publishes_then_downloads_one_media_batch(calls):
    module = x_module(dataset="dataset")
    module.configuration.app.dataset.media_batch_size = 7

    out = calls.run(maintenance.run_build_app(module, ctx=None))

    assert out == {"app": {"queries": 1}, "media": {"processed": 0}}
    assert calls == [
        ("publish", module.sync, True),
        ("media", (module.sync, 7), True),
    ]


def test_a_failed_publish_fails_the_build_without_a_media_batch(calls, monkeypatch):
    def publish(module, **kwargs):
        raise RuntimeError("storage is down")

    monkeypatch.setattr(maintenance, "publish_x_app", publish)
    with pytest.raises(RuntimeError, match="storage is down"):
        calls.run(maintenance.run_build_app(x_module(), ctx=None))
    assert calls == []


def test_the_compaction_is_skipped_while_the_dataset_sync_is_off(calls):
    out = calls.run(maintenance.run_compact_dataset(x_module(dataset="d"), ctx=None))
    assert out == {"skipped": "dataset sync disabled"} and calls == []


def test_the_compaction_compacts_the_module_dataset_off_the_loop(calls):
    module = x_module(dataset="dataset")
    module.configuration.app.dataset.sync_enabled = True

    out = calls.run(maintenance.run_compact_dataset(module, ctx=None))

    assert out == {"tables": ["posts_v1"]}
    assert calls == [("compact", "dataset", True)]
