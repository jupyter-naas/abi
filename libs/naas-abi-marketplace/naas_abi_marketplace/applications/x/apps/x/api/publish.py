"""Orchestrate publishing every X app snapshot + the Next.js web export."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.applications.x.apps.x.api.common import (
    DEFAULT_APP_PREFIX,
    DEFAULT_COUNT_GRAPH,
    DEFAULT_NAMESPACE,
    DEFAULT_TWEET_GRAPH,
    SnapshotContext,
    build_scenarios,
)
from naas_abi_marketplace.applications.x.apps.x.api.count_recent_tweets import (
    publish_page as publish_count_page,
)
from naas_abi_marketplace.applications.x.apps.x.api.globals import (
    publish_globals,
)
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import (
    publish_page as publish_search_page,
)
from naas_abi_marketplace.applications.x.apps.x.web.publish_assets import (
    upload_web_export,
)


def publish_app(
    object_storage: ObjectStorageService,
    triple_store: TripleStoreService,
    queries: list[dict[str, Any]],
    *,
    namespace: str = DEFAULT_NAMESPACE,
    app_prefix: str = DEFAULT_APP_PREFIX,
) -> dict[str, Any]:
    """Run every page/element script and publish the web static export."""
    built_at = datetime.now(UTC)
    scenarios = build_scenarios(built_at)
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
    )

    globals_doc = publish_globals(ctx)
    count_doc = publish_count_page(ctx)
    search_doc = publish_search_page(ctx)

    web = upload_web_export(object_storage, ctx.app_prefix)

    summary = {
        "app_prefix": ctx.app_prefix,
        "built_at": built_at.isoformat(),
        "scenarios": [s["id"] for s in scenarios],
        "queries": [
            q.get("slug")
            for q in (globals_doc.get("queries") or {}).get("queries", [])
        ],
        "pages": {
            "globals": list(globals_doc.keys()),
            "count_recent_tweets": list(count_doc.keys()),
            "search_recents_tweets": list(search_doc.keys()),
        },
        "web": web,
        "index_file": f"{ctx.app_prefix}/index.html",
    }
    logger.info(f"X app publish_app: done — {summary}")
    return summary
