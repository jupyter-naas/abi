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
from naas_abi_marketplace.applications.x.apps.x.api.search_users import (
    publish_page as publish_users_page,
)
from naas_abi_marketplace.applications.x.apps.x.web.publish_assets import (
    upload_web_export,
)


def _attach_cache(object_storage: ObjectStorageService):
    """A :class:`CacheReader` when a usable projection exists, else ``None``.

    Fails soft on purpose: polars may not be installed in every environment that
    imports this module, and the projection may not have been built yet. Either
    way the publish must still run off the graph.

    A projection written by an older ``SCHEMA_VERSION`` is refused rather than
    read. Its part files are missing columns this reader selects by name, so
    attaching one trades a clean fallback for a ``KeyError`` mid-publish. The
    next ``refresh`` rebuilds it at the current version — until then, SPARQL.
    """
    try:
        from naas_abi_marketplace.applications.x.apps.x.cache.reader import CacheReader
        from naas_abi_marketplace.applications.x.apps.x.cache.schema import (
            SCHEMA_VERSION,
        )
    except ImportError as exc:
        logger.info(f"X app publish: projection unavailable ({exc}) — using SPARQL")
        return None
    reader = CacheReader(object_storage)
    state = reader.projection_state()
    if not state or not state.get("watermark"):
        logger.info("X app publish: no projection published yet — using SPARQL")
        return None
    if state.get("schema_version") != SCHEMA_VERSION:
        logger.info(
            f"X app publish: projection is schema {state.get('schema_version')}, "
            f"this build reads {SCHEMA_VERSION} — using SPARQL until it is rebuilt"
        )
        return None
    logger.info(f"X app publish: using the Parquet projection ({state})")
    return reader


def publish_app(
    object_storage: ObjectStorageService,
    triple_store: TripleStoreService,
    queries: list[dict[str, Any]],
    *,
    namespace: str = DEFAULT_NAMESPACE,
    app_prefix: str = DEFAULT_APP_PREFIX,
    require_web: bool = True,
    full_users: bool = False,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Run every page/element script and publish the web static export.

    *require_web* false lets the run proceed when ``web/out/`` is absent — the
    orchestration path, where the image has no Node to build it. The CLI keeps
    it true so a forgotten ``pnpm build`` fails loudly instead of silently
    publishing snapshots against stale assets.

    *full_users* forces every Users shard to be rebuilt instead of only the
    ones whose authors changed; see ``api.search_users.users``.

    *use_cache* attaches the Parquet projection when one has been published, so
    the Users dataset is built from columnar data instead of two full-graph
    aggregates. It is advisory: an absent or unreadable projection simply leaves
    the SPARQL path in place.
    """
    built_at = datetime.now(UTC)
    scenarios = build_scenarios(built_at)
    cache = _attach_cache(object_storage) if use_cache else None
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
        cache=cache,
    )

    globals_doc = publish_globals(ctx)
    count_doc = publish_count_page(ctx)
    search_doc = publish_search_page(ctx)
    users_doc = publish_users_page(ctx, full=full_users)

    web = upload_web_export(object_storage, ctx.app_prefix, required=require_web)

    summary = {
        "app_prefix": ctx.app_prefix,
        "built_at": built_at.isoformat(),
        "scenarios": [s["id"] for s in scenarios],
        "queries": [
            q.get("slug") for q in (globals_doc.get("queries") or {}).get("queries", [])
        ],
        "pages": {
            "globals": list(globals_doc.keys()),
            "count_recent_tweets": list(count_doc.keys()),
            "search_recents_tweets": list(search_doc.keys()),
            # Counts rather than file names: the users dataset is 256 shards,
            # and how many of them actually changed is the useful signal when
            # this runs after every ingest tick. Carries ``skipped: true`` when
            # the tweet graph had not moved since the last publish.
            "search_users": users_doc,
        },
        "web": web,
        "index_file": f"{ctx.app_prefix}/index.html",
    }
    logger.info(f"X app publish_app: done — {summary}")
    return summary
