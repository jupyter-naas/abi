"""Tests for envelope storage vs envelopes_v1 bookkeeping."""

from __future__ import annotations

import json
from pathlib import Path

from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from signals.x.apps.x_proxy.cache.schema import ENVELOPE_PREFIX
from signals.x.apps.x_proxy.dataset.envelope_bookkeeping import (
    envelope_bookkeeping_diff,
)
from signals.x.apps.x_proxy.dataset.store import ENVELOPES_V1, X_DATASET_NAMESPACE


def _dataset(tmp_path: Path):
    return DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}",
        str(tmp_path / "warehouse"),
    )


def test_envelope_bookkeeping_diff_pending_and_in_sync(tmp_path: Path) -> None:
    storage = ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path))
    dataset = _dataset(tmp_path)
    # One level under ENVELOPE_PREFIX so FS list_objects finds the .json without
    # requiring directory markers with a trailing slash (MinIO often uses those).
    key = "2026-09-01T12_00_00Z_drones.json"
    storage.put_object(
        ENVELOPE_PREFIX,
        key,
        json.dumps({"query": "drones", "results": {"data": []}}).encode(),
    )
    rel = f"{ENVELOPE_PREFIX}/{key}"

    before = envelope_bookkeeping_diff(storage, dataset)
    assert before["storage_envelope_count"] == 1
    assert before["pending_ingest"] == [rel]
    assert before["in_sync"] is False

    from signals.x.apps.x_proxy.dataset.store import ensure_x_datasets

    ensure_x_datasets(dataset)
    dataset.write(
        ENVELOPES_V1,
        [
            {
                "envelope_path": rel,
                "query_slug": "drones",
                "ingested_at": "2026-09-01T12:00:00+00:00",
                "started_at": "",
                "ended_at": "",
            }
        ],
        namespace=X_DATASET_NAMESPACE,
        mode="upsert",
    )
    after = envelope_bookkeeping_diff(storage, dataset)
    assert after["pending_ingest"] == []
    assert after["ingested_not_in_storage"] == []
    assert after["in_sync"] is True
