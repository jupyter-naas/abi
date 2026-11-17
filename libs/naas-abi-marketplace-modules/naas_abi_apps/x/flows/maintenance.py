"""The bodies of the ``build_app`` and ``compact_dataset`` jobs.

Both jobs are ``skip_if_running``: a tick whose previous run is still going
ends SKIPPED before these bodies start. The work is synchronous (snapshots,
media downloads, dataset maintenance) and runs in worker threads, on
``module.sync``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from naas_abi_apps.x.flows.common import jsonable, publish_x_app
from naas_abi_apps.x.services import logger


def run_media_batch(sync: Any) -> dict:
    """Download one bounded batch of pending dataset media."""
    from naas_abi_apps.x.x_proxy.dataset.media_worker import (
        process_pending_media_batch,
    )

    app_cfg = getattr(sync.configuration, "app", None)
    dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
    batch = int(getattr(dataset_cfg, "media_batch_size", 4) or 4)
    result = process_pending_media_batch(sync, limit=batch)
    logger.info(f"X media batch: {result}")
    return result


def run_compaction(sync: Any) -> dict:
    """Compact the X dataset tables (a no-op while dataset sync is off)."""
    from naas_abi_apps.x.x_proxy.dataset.maintenance import compact_x_datasets
    from naas_abi_apps.x.x_proxy.dataset.store import x_dataset_sync_enabled

    if not x_dataset_sync_enabled(sync):
        logger.info("X dataset compaction: dataset sync disabled; skipped")
        return {"skipped": "dataset sync disabled"}
    report = compact_x_datasets(sync.engine.services.dataset)
    logger.info(f"X dataset compaction: done: {report}")
    return report


async def run_build_app(module: Any, ctx: Any) -> dict[str, Any]:
    """``build_app``: republish the Recent Tweets app (module ``app.publish``
    decides), then download one batch of pending media."""
    sync = module.sync
    app = await asyncio.to_thread(publish_x_app, sync)
    media = await asyncio.to_thread(run_media_batch, sync)
    return jsonable({"app": app, "media": media})


async def run_compact_dataset(module: Any, ctx: Any) -> dict[str, Any]:
    """``compact_dataset``: flush and compact each X dataset table."""
    return jsonable(await asyncio.to_thread(run_compaction, module.sync))
