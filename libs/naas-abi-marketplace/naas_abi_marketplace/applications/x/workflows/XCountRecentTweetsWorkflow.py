import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core.workflow.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
)
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    slugify_query,
)
from pydantic import Field

# X keeps only the last 7 days of recent tweets; stay just inside that window.
_MAX_LOOKBACK = timedelta(days=7)
# Query up to a round hour at least this far in the past so the integration's
# 15s end_time safety clamp never fires and every ingested bucket is a complete
# clock hour (a completed hour's count is final, which is what makes the
# per-hour dedupe in XCountRecentTweetsPipeline correct).
_END_SAFETY = timedelta(seconds=30)
_ISO_Z = "%Y-%m-%dT%H:%M:%SZ"


def _floor_hour(dt: datetime) -> datetime:
    """Round *dt* down to the start of its clock hour (UTC)."""
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _parse_iso(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class XCountRecentTweetsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for XCountRecentTweetsWorkflow.

    Attributes:
        x_integration: The XIntegration used to call the X v2 counts endpoint.
            Its responses are persisted to the datastore, which is what makes
            incremental (last-full-hour) runs possible.
        object_storage: Service used to read previously stored count envelopes so
            the workflow can recover the latest hour already fetched per query.
        datastore_path: Object-storage prefix under which the integration writes
            ``count_recent_tweets/<slug>/<timestamp>_<slug>.json`` envelopes.
        granularity: Bucket size requested from the counts endpoint. This
            workflow enforces round clock hours and is designed for "hour".
    """

    x_integration: XIntegration
    object_storage: ObjectStorageService
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )
    granularity: str = "hour"


class XCountRecentTweetsWorkflowParameters(WorkflowParameters):
    queries: Annotated[
        list[str],
        Field(
            ...,
            description=(
                "One or more X v2 search queries to follow. For each query the "
                "workflow fetches hourly tweet counts: the first run backfills "
                "the full 7-day window (up to 168 hourly buckets); every "
                "subsequent run only fetches the clock hours that have completed "
                "since the last stored bucket, so historical values are never "
                "recomputed."
            ),
            examples=[
                ["(drone OR drones OR uas OR uav) lang:en -is:retweet"],
            ],
        ),
    ]


class XCountRecentTweetsWorkflow(Workflow[XCountRecentTweetsWorkflowParameters]):
    """Follow hourly X tweet counts for one or more queries, incrementally.

    Round hours are enforced end-to-end: the fetch window is always bounded by
    two round clock hours, so every persisted bucket is a complete hour. The
    first run for a query backfills the whole 7-day window (24 × 7 hourly
    buckets); later runs resume from the hour after the newest stored bucket and
    fetch only the newly completed hours — a cheap way to keep the series fresh
    without recomputing the earlier buckets. The counts endpoint returns only
    time-bucketed totals (no tweet content) so it does not consume the
    tweet-retrieval budget.

    Queries are processed concurrently, one worker thread per query. Each fetch
    is persisted by the integration as a JSON envelope under
    ``<datastore>/count_recent_tweets/<slug>/``; the returned ``file_paths`` are
    what the orchestration then feeds to XCountRecentTweetsPipeline.
    """

    __configuration: XCountRecentTweetsWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: XCountRecentTweetsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    def _query_prefix(self, query: str) -> str:
        return os.path.join(
            self.__configuration.datastore_path,
            "count_recent_tweets",
            slugify_query(query),
        )

    def _latest_envelope(self, query: str) -> dict:
        """Newest persisted count envelope for *query*, or {} if none."""
        prefix = self._query_prefix(query)
        try:
            objects = self.__configuration.object_storage.list_objects(prefix)
        except Exception:
            return {}
        filenames = sorted(
            (os.path.basename(o) for o in objects if str(o).endswith(".json")),
            reverse=True,
        )
        for filename in filenames:
            data = self.__storage_utils.get_json(prefix, filename)
            if isinstance(data, dict):
                return data
        return {}

    def _latest_bucket_start(self, query: str) -> Optional[datetime]:
        """Newest bucket ``start`` already stored for *query* (round hour)."""
        envelope = self._latest_envelope(query)
        results = envelope.get("results") if isinstance(envelope, dict) else None
        buckets = (results or {}).get("data") if isinstance(results, dict) else None
        if not isinstance(buckets, list):
            return None
        starts = [
            dt
            for dt in (
                _parse_iso(b.get("start")) for b in buckets if isinstance(b, dict)
            )
            if dt is not None
        ]
        return max(starts) if starts else None

    def _resolve_window(
        self, query: str, now: datetime
    ) -> Optional[tuple[datetime, datetime, bool]]:
        """Return ``(start, end, is_backfill)`` round-hour window to fetch.

        ``None`` means the series is already up to date (nothing to fetch this
        tick). ``end`` is the exclusive upper bound — the most recent round hour
        that is safely in the past; every bucket below it is a complete hour.
        """
        end = _floor_hour(now - _END_SAFETY)
        # Earliest round hour still inside X's 7-day retention window.
        earliest = _floor_hour(now - _MAX_LOOKBACK) + timedelta(hours=1)
        if end <= earliest:
            return None

        latest_start = self._latest_bucket_start(query)
        if latest_start is None:
            return earliest, end, True

        # Resume from the hour after the newest stored bucket.
        start = max(latest_start + timedelta(hours=1), earliest)
        if start >= end:
            return None
        return start, end, False

    def _process_query(self, query: str, now: datetime) -> dict:
        window = self._resolve_window(query, now)
        if window is None:
            logger.info(
                f"XCountRecentTweetsWorkflow: query={query!r} already up to date"
            )
            return {
                "query": query,
                "fetched": False,
                "buckets": 0,
                "file_path": None,
                "start_time": None,
                "end_time": None,
            }

        start, end, is_backfill = window
        start_iso = start.strftime(_ISO_Z)
        end_iso = end.strftime(_ISO_Z)
        logger.info(
            f"XCountRecentTweetsWorkflow: query={query!r} "
            f"{'backfill' if is_backfill else 'incremental'} window "
            f"{start_iso} → {end_iso} "
            f"(granularity={self.__configuration.granularity})"
        )

        envelope = self.__configuration.x_integration.count_recent_tweets(
            query,
            start_time=start_iso,
            end_time=end_iso,
            granularity=self.__configuration.granularity,
        )
        results = envelope.get("results") if isinstance(envelope, dict) else {}
        buckets = (results or {}).get("data") or []
        return {
            "query": query,
            "fetched": True,
            "backfill": is_backfill,
            "buckets": len(buckets) if isinstance(buckets, list) else 0,
            "total_tweet_count": envelope.get("total_tweet_count"),
            "file_path": envelope.get("file_path"),
            "start_time": start_iso,
            "end_time": end_iso,
        }

    def run(self, parameters: XCountRecentTweetsWorkflowParameters) -> dict:
        if not isinstance(parameters, XCountRecentTweetsWorkflowParameters):
            raise ValueError(
                "Parameters must be of type XCountRecentTweetsWorkflowParameters"
            )
        queries = parameters.queries
        if not queries:
            return {"total_buckets": 0, "results": []}

        now = datetime.now(timezone.utc)
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            results = list(
                executor.map(lambda query: self._process_query(query, now), queries)
            )

        return {
            "total_buckets": sum(item["buckets"] for item in results),
            "file_paths": [
                item["file_path"] for item in results if item.get("file_path")
            ],
            "results": results,
        }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_follow_recent_tweet_counts",
                description=(
                    "Follow hourly X tweet counts for one or more queries. The "
                    "first run per query backfills the 7-day window; later runs "
                    "fetch only the newly completed clock hours. Returns, per "
                    "query, the number of buckets fetched and the persisted "
                    "count envelope file_path."
                ),
                func=lambda **kwargs: self.run(
                    XCountRecentTweetsWorkflowParameters(**kwargs)
                ),
                args_schema=XCountRecentTweetsWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None


if __name__ == "__main__":
    """Command-line entry point for XCountRecentTweetsWorkflow.

    ```
    abi dev up
    OXIGRAPH_URL=http://127.0.0.1:8432 uv run python \
        libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows/XCountRecentTweetsWorkflow.py \
        --queries '(drone OR drones OR uas OR uav) lang:en -is:retweet'
    ```
    """
    import argparse

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegrationConfiguration,
    )

    parser = argparse.ArgumentParser(
        description="Follow hourly X tweet counts for one or more queries."
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=["(drone OR drones OR uas OR uav) lang:en -is:retweet"],
        help="One or more X v2 search queries to follow.",
    )
    args = parser.parse_args()

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.x"])

    bearer_token = engine.services.secret.get("X_BEARER_TOKEN")
    datastore_path = ABIModule.get_instance().configuration.datastore_path
    x_integration = XIntegration(
        XIntegrationConfiguration(
            bearer_token=bearer_token, datastore_path=datastore_path
        )
    )

    workflow = XCountRecentTweetsWorkflow(
        XCountRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=engine.services.object_storage,
            datastore_path=datastore_path,
        )
    )
    output = workflow.run(XCountRecentTweetsWorkflowParameters(queries=args.queries))
    for item in output["results"]:
        state = "fetched" if item["fetched"] else "up-to-date"
        print(
            f"[{item['query'][:60]}…] {state} — {item['buckets']} bucket(s) "
            f"{item.get('start_time') or ''} → {item.get('end_time') or ''}"
        )
    print(f"Total buckets fetched: {output['total_buckets']}")
