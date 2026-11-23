"""The bodies of the ``build_app`` and ``compact_dataset`` jobs.

Both jobs are ``skip_if_running``: a tick whose previous run is still going
ends SKIPPED before these bodies start. The work is synchronous (snapshots,
media downloads, dataset maintenance) and runs on the module's threads
(``module.sync.call``). Also the start-up upload of the web export
(``publish_web_export_at_start``).
"""

from __future__ import annotations

import asyncio
from typing import Any

from naas_abi_apps.x.flows.common import (
    jsonable,
    publish_x_app,
    x_app_publish_enabled,
)
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
    app = await sync.call(publish_x_app, sync)
    media = await sync.call(run_media_batch, sync)
    return jsonable({"app": app, "media": media})


async def run_compact_dataset(module: Any, ctx: Any) -> dict[str, Any]:
    """``compact_dataset``: flush and compact each X dataset table."""
    sync = module.sync
    return jsonable(await sync.call(run_compaction, sync))


def _publish_web_export(sync: Any) -> dict[str, Any]:
    from naas_abi_apps.x.x_proxy import build

    if not x_app_publish_enabled(sync):
        return {"skipped": True, "reason": "app.publish=false"}
    return build.publish_web_export(sync, required=False)


async def publish_web_export_at_start(module: Any) -> dict[str, Any] | None:
    """Upload the web export this process carries (the image's), at module start.

    The export in object storage is the one an earlier version published, and
    only a publish replaces it, which ``build_app`` does only with
    ``app.dataset.read_enabled``: after an upgrade the app would serve the old
    export. Runs in the background (``ABIModule.on_initialized``): READY never
    waits for it, and a failure is only logged (``None``). Unchanged files are
    not uploaded again (the export's manifest). ``app.publish`` false skips it.
    """
    sync = module.sync
    try:
        summary = await sync.call(_publish_web_export, sync)
    except asyncio.CancelledError:
        raise
    except Exception as error:  # noqa: BLE001 - the app keeps the export it has
        logger.warning(f"X app: web export not published at start ({error})")
        return None
    logger.info(f"X app: web export at start: {summary}")
    return jsonable(summary)
