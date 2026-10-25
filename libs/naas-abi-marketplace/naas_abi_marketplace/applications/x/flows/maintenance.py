"""The dataset maintenance bodies shared by the Dagster ops and the durable jobs."""

from __future__ import annotations

from naas_abi_core import logger


def run_media_batch(module) -> dict:
    """Download one bounded batch of pending dataset media."""
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_worker import (
        process_pending_media_batch,
    )

    app_cfg = getattr(module.configuration, "app", None)
    dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
    batch = int(getattr(dataset_cfg, "media_batch_size", 4) or 4)
    result = process_pending_media_batch(module, limit=batch)
    logger.info(f"X media batch — {result}")
    return result


def run_compaction(module) -> dict:
    """Compact the X Dataset Service tables (a no-op while dataset sync is off)."""
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.maintenance import (
        compact_x_datasets,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
        x_dataset_sync_enabled,
    )

    if not x_dataset_sync_enabled(module):
        logger.info("X dataset compaction: dataset sync disabled; skipped")
        return {"skipped": "dataset sync disabled"}
    report = compact_x_datasets(module.engine.services.dataset)
    logger.info(f"X dataset compaction: done — {report}")
    return report
