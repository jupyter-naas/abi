"""The ``build_app`` and ``compact_dataset`` job bodies: off the loop, on ``module.sync``."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from naas_abi_apps.common.testing import FakeTripleStore
from naas_abi_apps.x.flows import maintenance
from naas_abi_apps.x.flows.conftest import real_x_module, x_module
from naas_abi_apps.x.x_proxy import build
from naas_abi_apps.x.x_proxy.dataset import maintenance as dataset_maintenance
from naas_abi_apps.x.x_proxy.dataset import media_worker
from naas_abi_apps.x.x_proxy.testing import on_sync_thread


class Calls(list):
    """What the stubbed app, media worker and dataset did, and from which thread."""

    run: Any


@pytest.fixture
def calls(monkeypatch):
    calls = Calls()

    def off_loop() -> bool:
        # On the module's threads: not the loop, not its default executor.
        return on_sync_thread()

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

    calls.run = asyncio.run
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


# --- the web export at start -------------------------------------------------------


def test_the_web_export_is_uploaded_at_start_on_the_module_threads(monkeypatch):
    seen: list[Any] = []

    def publish(sync, *, required):
        seen.append((sync, required, on_sync_thread()))
        return {"uploaded": 3}

    monkeypatch.setattr(build, "publish_web_export", publish)
    module = x_module(object_storage="storage")
    # Without the dataset read path (the default): the export still goes up.
    assert module.configuration.app.dataset.read_enabled is False

    out = asyncio.run(maintenance.publish_web_export_at_start(module))

    assert out == {"uploaded": 3}
    assert seen == [(module.sync, False, True)]


def test_a_failed_upload_at_start_is_only_logged(monkeypatch, caplog):
    def publish(sync, *, required):
        raise RuntimeError("storage is down")

    monkeypatch.setattr(build, "publish_web_export", publish)
    out = asyncio.run(maintenance.publish_web_export_at_start(x_module()))
    assert out is None
    assert "storage is down" in caplog.text


def test_no_upload_at_start_when_the_app_is_not_published(monkeypatch):
    monkeypatch.setattr(build, "publish_web_export", pytest.fail)
    module = x_module()
    module.configuration.app.publish = False
    out = asyncio.run(maintenance.publish_web_export_at_start(module))
    assert out == {"skipped": True, "reason": "app.publish=false"}


def test_the_module_starts_without_waiting_for_the_upload_and_cancels_it(
    monkeypatch,
):
    """``on_initialized`` returns (READY) while the upload runs; ``on_unloaded``
    cancels it before it closes the module's threads."""
    import threading

    started, release = threading.Event(), threading.Event()

    def publish(sync, *, required):
        started.set()
        release.wait(5)
        return {"uploaded": 0}

    monkeypatch.setattr(build, "publish_web_export", publish)
    module = real_x_module()
    module.engine.services.triple_store = FakeTripleStore()

    async def scenario() -> asyncio.Task:
        await module.on_initialized()
        task = module._web_export
        assert await asyncio.to_thread(started.wait, 5)
        assert not task.done()
        await module.on_unloaded()
        return task

    try:
        task = asyncio.run(scenario())
    finally:
        release.set()
    assert task.cancelled()
    assert module.sync.executor._shutdown
