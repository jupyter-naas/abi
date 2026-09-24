"""Orchestrate publishing every X app snapshot + the Next.js web export."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_APP_PREFIX,
    DEFAULT_COUNT_GRAPH,
    DEFAULT_NAMESPACE,
    DEFAULT_TWEET_GRAPH,
    SnapshotContext,
    build_scenarios,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.count_recent_tweets import (
    publish_page as publish_count_page,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.globals import (
    publish_globals,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_recents_tweets import (
    publish_page as publish_search_page,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.snapshot_reader import (
    DatasetSnapshotReader,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.web.publish_assets import (
    upload_web_export,
)


def _dataset_data_start(dataset: IDatasetPort) -> datetime | None:
    """Earliest post timestamp in ``posts_v1``, for All-time scenario bounds."""
    try:
        ensure_x_datasets(dataset)
        result = dataset.query(
            f"SELECT MIN(created_at) AS mn FROM {POSTS_V1}",  # nosec B608
            namespace=X_DATASET_NAMESPACE,
        )
        if not result.rows:
            return None
        raw = result.rows[0].get("mn")
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
        text = str(raw)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        return datetime.fromisoformat(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"X app publish: could not read dataset data_start ({exc})")
        return None


def publish_app(
    object_storage: ObjectStorageService,
    triple_store: TripleStoreService,
    queries: list[dict[str, Any]],
    *,
    dataset: IDatasetPort,
    namespace: str = DEFAULT_NAMESPACE,
    app_prefix: str = DEFAULT_APP_PREFIX,
    require_web: bool = True,
) -> dict[str, Any]:
    """Run every page script and publish the web static export from Dataset Service.

    Tweet/user search is served live from dataset HTTP routes; this publish writes
    globals plus count/search dashboard snapshots (KPIs, charts, tables, facets).

    *require_web* false lets the run proceed when ``web/out/`` is absent - the
    orchestration path, where the image has no Node to build it.
    """
    built_at = datetime.now(UTC)
    reader = DatasetSnapshotReader(dataset)
    data_start = reader.earliest_matched_created_at() or _dataset_data_start(dataset)
    scenarios = build_scenarios(built_at, data_start=data_start)
    ctx = SnapshotContext(
        object_storage,
        triple_store,
        queries=queries,
        scenarios=scenarios,
        graph_name=DEFAULT_COUNT_GRAPH,
        tweet_graph_name=DEFAULT_TWEET_GRAPH,
        namespace=namespace,
        app_prefix=app_prefix,
        built_at=built_at,
        cache=reader,
        dataset=dataset,
    )

    count_doc = publish_count_page(ctx)
    search_doc = publish_search_page(ctx)
    globals_doc = publish_globals(ctx)
    tweets_doc = {"skipped": True, "reason": "dataset_live_search"}
    users_doc = {"skipped": True, "reason": "dataset_live_search"}

    web = upload_web_export(object_storage, ctx.app_prefix, required=require_web)

    summary = {
        "app_prefix": ctx.app_prefix,
        "built_at": built_at.isoformat(),
        "mode": "dataset",
        "scenarios": [s["id"] for s in scenarios],
        "queries": [
            q.get("slug") for q in (globals_doc.get("queries") or {}).get("queries", [])
        ],
        "pages": {
            "globals": list(globals_doc.keys()),
            "count_recent_tweets": list(count_doc.keys()),
            "search_recents_tweets": list(search_doc.keys()),
            "search_tweets": tweets_doc,
            "search_users": users_doc,
        },
        "web": web,
        "index_file": f"{ctx.app_prefix}/index.html",
    }
    logger.info(f"X app publish_app: done - {summary}")
    return summary
