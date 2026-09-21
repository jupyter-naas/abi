"""Dataset Service table specs and helpers for the X Proxy read model."""

from __future__ import annotations

import json
from typing import Any

from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetAlreadyExistsError,
    DatasetSpec,
    IDatasetPort,
    PartitionSpec,
)

X_DATASET_NAMESPACE = "x"

POSTS_V1 = "posts_v1"
MATCHED_TWEET_IDS_V1 = "matched_tweet_ids_v1"
AUTHORS_V1 = "authors_v1"
AUTHOR_STATS_V1 = "author_stats_v1"
ENVELOPES_V1 = "envelopes_v1"
MEDIA_V1 = "media_v1"
POST_MEDIA_V1 = "post_media_v1"
COUNT_BUCKETS_V1 = "count_buckets_v1"
PROJECTION_COMMITS_V1 = "projection_commits_v1"

MEDIA_OBJECT_PREFIX = "x/media"

_DATASET_SPEC_COMMENT_PREFIX = "abi.dataset-spec:"


def _author_stats_v1_spec() -> DatasetSpec:
    return DatasetSpec(
        name=AUTHOR_STATS_V1,
        namespace=X_DATASET_NAMESPACE,
        columns=(
            ColumnSpec(name="author_id", type="string"),
            ColumnSpec(name="matched_count", type="integer"),
            ColumnSpec(name="referenced_count", type="integer"),
            ColumnSpec(name="first_post_at", type="timestamp"),
            ColumnSpec(name="last_post_at", type="timestamp"),
            ColumnSpec(name="updated_at", type="timestamp"),
        ),
        primary_key=("author_id",),
    )


def _refresh_dataset_table_comment(dataset: IDatasetPort, spec: DatasetSpec) -> None:
    """Keep DuckLake table COMMENT in sync with code (writes validate against it)."""
    comment = _DATASET_SPEC_COMMENT_PREFIX + json.dumps(
        spec.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    escaped = comment.replace("'", "''")
    dataset.query(
        f"COMMENT ON TABLE {spec.name} IS '{escaped}'",  # nosec B608
        namespace=spec.namespace,
    )


def x_dataset_sync_enabled(module) -> bool:
    """True when module config enables dataset sync and Dataset Service is wired."""
    app_cfg = getattr(module.configuration, "app", None)
    dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
    if dataset_cfg is None or not getattr(dataset_cfg, "sync_enabled", False):
        return False
    try:
        return getattr(module.engine.services, "dataset", None) is not None
    except Exception:  # noqa: BLE001
        return False


def x_dataset_read_enabled(module) -> bool:
    app_cfg = getattr(module.configuration, "app", None)
    dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
    if dataset_cfg is None or not getattr(dataset_cfg, "read_enabled", False):
        return False
    try:
        return getattr(module.engine.services, "dataset", None) is not None
    except Exception:  # noqa: BLE001
        return False


def ensure_x_datasets(dataset: IDatasetPort) -> None:
    specs = (
        DatasetSpec(
            name=POSTS_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="tweet_id", type="string"),
                ColumnSpec(name="kind", type="string"),
                ColumnSpec(name="query_slug", type="string"),
                ColumnSpec(name="created_at", type="timestamp"),
                ColumnSpec(name="created_month", type="string"),
                ColumnSpec(name="author_id", type="string"),
                ColumnSpec(name="text", type="string"),
                ColumnSpec(name="full_text", type="string"),
                ColumnSpec(name="lang", type="string"),
                ColumnSpec(name="conversation_id", type="string"),
                ColumnSpec(name="like_count", type="integer"),
                ColumnSpec(name="retweet_count", type="integer"),
                ColumnSpec(name="reply_count", type="integer"),
                ColumnSpec(name="media_urls", type="string"),
            ),
            partitions=(PartitionSpec(column="created_month", transform="identity"),),
            primary_key=("tweet_id", "kind", "query_slug"),
        ),
        DatasetSpec(
            name=MATCHED_TWEET_IDS_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(ColumnSpec(name="tweet_id", type="string"),),
            primary_key=("tweet_id",),
        ),
        DatasetSpec(
            name=AUTHORS_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="author_id", type="string"),
                ColumnSpec(name="username", type="string"),
                ColumnSpec(name="display_name", type="string"),
                ColumnSpec(name="description", type="string"),
                ColumnSpec(name="location", type="string"),
                ColumnSpec(name="verified_type", type="string"),
                ColumnSpec(name="verified", type="boolean"),
                ColumnSpec(name="protected", type="boolean"),
                ColumnSpec(name="is_identity_verified", type="boolean"),
                ColumnSpec(name="user_url", type="string"),
                ColumnSpec(name="profile_image_url", type="string"),
                ColumnSpec(name="profile_banner_url", type="string"),
                ColumnSpec(name="user_created_at", type="string"),
                ColumnSpec(name="most_recent_tweet_id", type="string"),
                ColumnSpec(name="followers_count", type="integer"),
                ColumnSpec(name="following_count", type="integer"),
                ColumnSpec(name="tweet_count", type="integer"),
                ColumnSpec(name="listed_count", type="integer"),
                ColumnSpec(name="user_like_count", type="integer"),
                ColumnSpec(name="media_count", type="integer"),
                ColumnSpec(name="seen_at", type="string"),
            ),
            primary_key=("author_id",),
        ),
        _author_stats_v1_spec(),
        DatasetSpec(
            name=ENVELOPES_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="envelope_path", type="string"),
                ColumnSpec(name="query_slug", type="string"),
                ColumnSpec(name="ingested_at", type="timestamp"),
                ColumnSpec(name="started_at", type="string"),
                ColumnSpec(name="ended_at", type="string"),
            ),
            primary_key=("envelope_path",),
        ),
        DatasetSpec(
            name=MEDIA_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="media_key", type="string"),
                ColumnSpec(name="media_type", type="string"),
                ColumnSpec(name="source_url", type="string"),
                ColumnSpec(name="preview_url", type="string"),
                ColumnSpec(name="status", type="string"),
                ColumnSpec(name="storage_key", type="string"),
                ColumnSpec(name="sha256", type="string"),
                ColumnSpec(name="byte_size", type="integer"),
                ColumnSpec(name="last_error", type="string"),
                ColumnSpec(name="updated_at", type="timestamp"),
            ),
            primary_key=("media_key",),
        ),
        DatasetSpec(
            name=POST_MEDIA_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="tweet_id", type="string"),
                ColumnSpec(name="media_key", type="string"),
                ColumnSpec(name="ordinal", type="integer"),
            ),
            primary_key=("tweet_id", "media_key"),
        ),
        DatasetSpec(
            name=COUNT_BUCKETS_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="query_slug", type="string"),
                ColumnSpec(name="bucket_start", type="string"),
                ColumnSpec(name="bucket_end", type="string"),
                ColumnSpec(name="tweet_count", type="integer"),
                ColumnSpec(name="source_path", type="string"),
            ),
            primary_key=("query_slug", "bucket_start", "bucket_end"),
        ),
        DatasetSpec(
            name=PROJECTION_COMMITS_V1,
            namespace=X_DATASET_NAMESPACE,
            columns=(
                ColumnSpec(name="commit_id", type="string"),
                ColumnSpec(name="committed_at", type="timestamp"),
                ColumnSpec(name="envelope_count", type="integer"),
                ColumnSpec(name="active", type="boolean"),
                ColumnSpec(name="detail", type="json"),
            ),
            primary_key=("commit_id",),
        ),
    )
    for spec in specs:
        try:
            dataset.create(spec)
        except DatasetAlreadyExistsError:
            # Catalog import / replay can register tables without abi.dataset-spec COMMENT.
            _refresh_dataset_table_comment(dataset, spec)
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
        ensure_matched_tweet_ids_ready,
    )

    ensure_matched_tweet_ids_ready(dataset)
    _migrate_x_dataset_schema(dataset)


def _migrate_x_dataset_schema(dataset: IDatasetPort) -> None:
    """Apply additive schema fixes on existing DuckLake tables."""
    described = dataset.query(
        f"DESCRIBE {AUTHOR_STATS_V1}",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    columns = {
        str(row.get("column_name") or row.get("Field") or "").strip().lower()
        for row in described.rows
    }
    if "first_post_at" not in columns:
        dataset.query(
            f"ALTER TABLE {AUTHOR_STATS_V1} ADD COLUMN first_post_at TIMESTAMP",  # nosec B608
            namespace=X_DATASET_NAMESPACE,
        )
    _refresh_dataset_table_comment(dataset, _author_stats_v1_spec())


TABLE_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    POSTS_V1: ("tweet_id", "kind", "query_slug"),
    MATCHED_TWEET_IDS_V1: ("tweet_id",),
    AUTHORS_V1: ("author_id",),
    AUTHOR_STATS_V1: ("author_id",),
    ENVELOPES_V1: ("envelope_path",),
    MEDIA_V1: ("media_key",),
    POST_MEDIA_V1: ("tweet_id", "media_key"),
    COUNT_BUCKETS_V1: ("query_slug", "bucket_start", "bucket_end"),
    PROJECTION_COMMITS_V1: ("commit_id",),
}


def dedupe_rows(
    rows: list[dict[str, Any]],
    key_columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Last row wins per primary key (DuckLake upsert rejects dupes in one batch)."""
    if not key_columns or not rows:
        return rows
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(column) for column in key_columns)
        merged[key] = row
    return list(merged.values())


def upsert_table(
    dataset: IDatasetPort,
    table: str,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    ensure_x_datasets(dataset)
    key_columns = TABLE_PRIMARY_KEYS.get(table, ())
    unique_rows = dedupe_rows(rows, key_columns)
    dataset.write(table, unique_rows, namespace=X_DATASET_NAMESPACE, mode="upsert")
    return len(unique_rows)


def envelope_already_ingested(dataset: IDatasetPort, envelope_path: str) -> bool:
    ensure_x_datasets(dataset)
    escaped = envelope_path.replace("'", "''")
    result = dataset.query(
        f"SELECT envelope_path FROM {ENVELOPES_V1} WHERE envelope_path = '{escaped}' LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    return bool(result.rows)
