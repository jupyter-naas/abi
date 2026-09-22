"""Compare object-storage search_recent_tweets envelopes vs ``envelopes_v1``."""

from __future__ import annotations

from typing import Any

from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from signals.x.apps.x_proxy.cache.schema import ENVELOPE_PREFIX
from signals.x.apps.x_proxy.cache.storage import walk
from signals.x.apps.x_proxy.dataset.store import (
    ENVELOPES_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)


def normalize_envelope_path(path: str) -> str:
    return str(path or "").strip().lstrip("/")


def list_storage_envelope_paths(
    object_storage: ObjectStorageService,
    *,
    envelope_prefix: str = ENVELOPE_PREFIX,
) -> list[str]:
    paths = walk(object_storage, envelope_prefix.strip("/"), suffix=".json")
    normalized = [normalize_envelope_path(p) for p in paths if p]
    return sorted(set(normalized))


def list_ingested_envelope_paths(dataset: IDatasetPort) -> list[str]:
    ensure_x_datasets(dataset)
    result = dataset.query(
        f"SELECT envelope_path FROM {ENVELOPES_V1} ORDER BY envelope_path",
        namespace=X_DATASET_NAMESPACE,
    )
    paths = [
        normalize_envelope_path(str(row["envelope_path"]))
        for row in result.rows
        if row.get("envelope_path")
    ]
    return sorted(set(paths))


def envelope_bookkeeping_diff(
    object_storage: ObjectStorageService,
    dataset: IDatasetPort,
    *,
    envelope_prefix: str = ENVELOPE_PREFIX,
) -> dict[str, Any]:
    """Diff envelope JSON in object storage vs rows in ``x.envelopes_v1``."""
    storage_paths = list_storage_envelope_paths(
        object_storage, envelope_prefix=envelope_prefix
    )
    ingested_paths = list_ingested_envelope_paths(dataset)
    storage_set = set(storage_paths)
    ingested_set = set(ingested_paths)
    pending_ingest = [p for p in storage_paths if p not in ingested_set]
    ingested_not_in_storage = sorted(ingested_set - storage_set)
    prefix = normalize_envelope_path(envelope_prefix)
    return {
        "envelope_prefix": prefix,
        "storage_envelope_count": len(storage_paths),
        "ingested_envelope_count": len(ingested_paths),
        "pending_ingest": pending_ingest,
        "ingested_not_in_storage": ingested_not_in_storage,
        "in_sync": not pending_ingest and not ingested_not_in_storage,
    }
