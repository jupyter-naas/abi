"""Compatibility facade for the X Recent Tweets app hub.

Prefer ``api.publish.publish_app`` and the per-page scripts under
``api/``. This module keeps the ``XAppHubBuilder`` / ``slugify`` import
surface used by orchestrations and tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_APP_PREFIX,
    DEFAULT_COUNT_GRAPH,
    DEFAULT_NAMESPACE,
    DEFAULT_TWEET_GRAPH,
    DEFAULT_TWEET_LIMIT,
    SnapshotContext,
    slugify,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.publish import publish_app

# Re-exports for existing callers / tests.
__all__ = [
    "APP_HTML_DATA_BASE",
    "DEFAULT_APP_PREFIX",
    "DEFAULT_COUNT_GRAPH",
    "DEFAULT_NAMESPACE",
    "DEFAULT_TWEET_GRAPH",
    "DEFAULT_TWEET_LIMIT",
    "XAppHubBuilder",
    "slugify",
]

APP_HTML_DATA_BASE = "/app-html/x/apps/x_proxy"


class XAppHubBuilder:
    """Publish the X dashboard + typed JSON snapshots to object storage."""

    def __init__(
        self,
        object_storage_service: ObjectStorageService,
        triple_store: TripleStoreService,
        *,
        graph_name: str = DEFAULT_COUNT_GRAPH,
        tweet_graph_name: str = DEFAULT_TWEET_GRAPH,
        namespace: str = DEFAULT_NAMESPACE,
        app_prefix: str = DEFAULT_APP_PREFIX,
    ) -> None:
        self._object_storage = object_storage_service
        self._triple_store = triple_store
        self.graph_name = graph_name
        self.tweet_graph_name = tweet_graph_name
        self.namespace = namespace
        self.app_prefix = app_prefix.rstrip("/")
        self._ctx = SnapshotContext(
            object_storage_service,
            triple_store,
            queries=[],
            graph_name=graph_name,
            tweet_graph_name=tweet_graph_name,
            namespace=namespace,
            app_prefix=app_prefix,
        )

    def _timeseries(self, query_string: str) -> list[dict[str, Any]]:
        return self._ctx.timeseries(query_string)

    def _tweets(
        self, query_string: str, limit: int = DEFAULT_TWEET_LIMIT
    ) -> list[dict[str, Any]]:
        # Compatibility: return newest tweets without a time filter (full lookback
        # capped by LIMIT). Prefer SnapshotContext.tweets_in_window for scenarios.
        from datetime import UTC, datetime, timedelta

        end = datetime.now(UTC)
        start = end - timedelta(days=30)
        return self._ctx.tweets_in_window(
            query_string,
            start.isoformat(),
            end.isoformat(),
            limit=limit,
        )

    def publish(
        self, queries: Iterable[dict[str, Any]], *, full_users: bool = False
    ) -> dict[str, Any]:
        """Publish snapshots (+ web assets when this host has an export).

        Called from the orchestration, which runs in an image without Node, so
        a missing ``web/out/`` skips the asset upload instead of failing the
        whole run — the snapshot refresh is what the schedule is for.

        *full_users* forces a complete Users-dataset rebuild; the default only
        rebuilds the shards whose authors changed.
        """
        return publish_app(
            self._object_storage,
            self._triple_store,
            list(queries),
            namespace=self.namespace,
            app_prefix=self.app_prefix,
            require_web=False,
            full_users=full_users,
        )
