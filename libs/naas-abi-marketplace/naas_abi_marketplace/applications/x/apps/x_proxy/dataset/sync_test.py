"""Tests for envelope → dataset sync."""

from __future__ import annotations

import json

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.schema import (
    ENVELOPE_PREFIX,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
    ENVELOPES_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.sync import (
    sync_envelope_paths,
)


@pytest.fixture
def dataset(tmp_path):
    return DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}",
        str(tmp_path / "warehouse"),
    )


class _FakeStorage:
    def __init__(self, objects: dict[tuple[str, str], bytes]) -> None:
        self._objects = objects

    def get_object(self, prefix: str, key: str) -> bytes:
        return self._objects[(prefix, key)]


class _FakeEngine:
    def __init__(self, dataset, storage) -> None:
        self.services = type(
            "Services",
            (),
            {"dataset": dataset, "object_storage": storage},
        )()


class _FakeDatasetCfg:
    sync_enabled = True


class _FakeAppCfg:
    dataset = _FakeDatasetCfg()


class _FakeConfig:
    app = _FakeAppCfg()


class _FakeModule:
    configuration = _FakeConfig()

    def __init__(self, dataset, storage) -> None:
        self.engine = _FakeEngine(dataset, storage)


def _sample_envelope() -> dict:
    return {
        "query": "drones lang:en",
        "started_at": "2026-09-01T12:00:00+00:00",
        "ended_at": "2026-09-01T12:01:00+00:00",
        "results": {
            "data": [
                {
                    "id": "100",
                    "author_id": "42",
                    "created_at": "2026-09-01T11:00:00+00:00",
                    "text": "hello drone",
                    "public_metrics": {},
                }
            ],
            "includes": {
                "users": [
                    {
                        "id": "42",
                        "username": "pilot1",
                        "name": "Pilot",
                        "public_metrics": {},
                    }
                ],
                "media": [],
                "tweets": [],
            },
        },
    }


def test_sync_envelope_paths_idempotent(dataset):
    ensure_x_datasets(dataset)
    rel = "x/search_recent_tweets/drones/2026-09-01T12_00_00.json"
    prefix, key = ENVELOPE_PREFIX, rel.split("/", 2)[-1]
    # key is drones/2026-09-01...
    prefix = "x/search_recent_tweets/drones"
    key = "2026-09-01T12_00_00.json"
    body = json.dumps(_sample_envelope()).encode()
    storage = _FakeStorage({(prefix, key): body})
    module = _FakeModule(dataset, storage)
    path = f"{prefix}/{key}"

    first = sync_envelope_paths(module, [path])
    assert first["ingested_envelopes"] == 1
    assert first["posts_upserted"] == 1

    second = sync_envelope_paths(module, [path])
    assert second["skipped_envelopes"] == 1
    assert second["ingested_envelopes"] == 0

    rows = dataset.query(
        f"SELECT COUNT(*) AS n FROM {POSTS_V1}",
        namespace=X_DATASET_NAMESPACE,
    )
    assert int(rows.rows[0]["n"]) == 1
    env_rows = dataset.query(
        f"SELECT COUNT(*) AS n FROM {ENVELOPES_V1}",
        namespace=X_DATASET_NAMESPACE,
    )
    assert int(env_rows.rows[0]["n"]) == 1
    stats = dataset.query(
        f"SELECT first_post_at, last_post_at, matched_count FROM {AUTHOR_STATS_V1}",
        namespace=X_DATASET_NAMESPACE,
    )
    assert len(stats.rows) == 1
    assert int(stats.rows[0]["matched_count"]) == 1
    assert stats.rows[0]["first_post_at"] is not None


def test_sync_dedupes_duplicate_posts_in_one_batch(dataset):
    """Same tweet in two envelopes in one sync batch must not fail upsert."""
    ensure_x_datasets(dataset)
    prefix = "x/search_recent_tweets/drones"
    body = json.dumps(_sample_envelope()).encode()
    paths = [
        f"{prefix}/2026-09-01T12_00_00.json",
        f"{prefix}/2026-09-01T12_05_00.json",
    ]
    storage = _FakeStorage({(prefix, p.rsplit("/", 1)[-1]): body for p in paths})
    module = _FakeModule(dataset, storage)

    summary = sync_envelope_paths(module, paths)
    assert summary["ingested_envelopes"] == 2
    assert summary["posts_upserted"] == 1

    rows = dataset.query(
        f"SELECT COUNT(*) AS n FROM {POSTS_V1}",
        namespace=X_DATASET_NAMESPACE,
    )
    assert int(rows.rows[0]["n"]) == 1
