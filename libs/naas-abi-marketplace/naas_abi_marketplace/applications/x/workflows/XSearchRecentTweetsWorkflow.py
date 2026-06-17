import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
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
from rdflib import URIRef

# Recognised keyword arguments accepted by XIntegration.search_recent_tweets,
# minus ``since_id`` which this workflow derives per query from the datastore.
_SEARCH_OPTION_KEYS = frozenset(
    {
        "start_time",
        "end_time",
        "until_id",
        "max_results",
        "sort_order",
        "tweet_fields",
        "expansions",
        "media_fields",
        "poll_fields",
        "user_fields",
        "place_fields",
        "max_pages",
    }
)


@dataclass
class XSearchRecentTweetsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for XSearchRecentTweetsWorkflow.

    Attributes:
        x_integration: The XIntegration used to call the X v2 recent-search
            endpoint. Its responses are persisted to the datastore, which is
            what makes incremental (since_id) runs possible.
        object_storage: Service used to read previously stored responses so the
            workflow can recover each query's ``since_id``.
        triple_store: Engine triple store, retained for callers that wire it
            explicitly. Defaults to the engine's triple store.
        datastore_path: Object-storage prefix under which the integration writes
            ``search_recent_tweets/<slug>/<timestamp>_<slug>.json`` files.
        graph_name: Named graph associated with this workflow's data.
    """

    x_integration: XIntegration
    object_storage: ObjectStorageService
    triple_store: TripleStoreService = field(
        default_factory=lambda: ABIModule.get_instance().engine.services.triple_store
    )
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )
    graph_name: URIRef = field(
        default_factory=lambda: URIRef(
            ABIModule.get_instance().configuration.graph_name
        )
    )


class XSearchRecentTweetsWorkflowParameters(WorkflowParameters):
    queries: Annotated[
        list[str],
        Field(
            ...,
            description=(
                "One or more X v2 search queries to run. Each query is fetched "
                "incrementally: the workflow looks up the highest tweet id "
                "already stored for that query (since_id) and only returns "
                "tweets newer than it."
            ),
            examples=[
                [
                    '("rogue drone" OR "drone threat") ("World Cup" OR "FIFA") lang:en -is:retweet',
                    '("unauthorized drone" OR "airspace violation") ("stadium") lang:en -is:retweet',
                ]
            ],
        ),
    ]
    options: Annotated[
        Optional[dict],
        Field(
            default_factory=dict,
            description=(
                "Optional keyword arguments forwarded to "
                "XIntegration.search_recent_tweets for every query — any subset "
                "of: start_time, end_time, until_id, max_results, sort_order, "
                "tweet_fields, expansions, media_fields, poll_fields, "
                "user_fields, place_fields, max_pages. 'since_id' is not "
                "accepted here; it is derived per query from the datastore."
            ),
            examples=[{"max_results": 100, "sort_order": "recency", "max_pages": None}],
        ),
    ]
    persist: Annotated[
        bool,
        Field(
            description=(
                "Whether the per-query pipeline inserts the generated tweet "
                "graph into the configured triple store. Set False to fetch and "
                "persist the JSON envelopes (and build the graphs) without "
                "writing to the triple store."
            ),
        ),
    ] = True


class XSearchRecentTweetsWorkflow(Workflow[XSearchRecentTweetsWorkflowParameters]):
    """Run several X recent-search queries incrementally.

    For every query the workflow recovers a ``since_id`` from the datastore (the
    highest tweet id seen on a previous run) and asks X only for newer tweets.
    The integration persists each response, so the cursor advances on its own:
    the first run fetches the last 7 days, and every subsequent run returns only
    what appeared since. ``since_id`` is read by scanning the per-query folder
    newest-to-oldest and taking the first ``results.meta.newest_id`` found, so a
    run that returned zero new tweets (no ``newest_id``) does not reset it.

    Queries are processed concurrently, one worker thread per query, so a batch
    of N queries runs its N fetch passes in parallel.
    """

    __configuration: XSearchRecentTweetsWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: XSearchRecentTweetsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    def get_since_id(self, query: str) -> Optional[str]:
        """Return the highest tweet id already fetched for ``query``, or None.

        Scans ``<datastore_path>/search_recent_tweets/<slug>/`` from the newest
        file to the oldest and returns the first ``results.meta.newest_id`` it
        finds. Returns None on the first run for a query (no folder yet).
        """
        prefix = os.path.join(
            self.__configuration.datastore_path,
            "search_recent_tweets",
            slugify_query(query),
        )
        try:
            objects = self.__configuration.object_storage.list_objects(prefix)
        except Exception:
            return None

        filenames = sorted(
            (os.path.basename(o) for o in objects if o.endswith(".json")),
            reverse=True,
        )
        for filename in filenames:
            data = self.__storage_utils.get_json(prefix, filename)
            results = data.get("results") if isinstance(data, dict) else None
            meta = results.get("meta") if isinstance(results, dict) else None
            newest_id = meta.get("newest_id") if isinstance(meta, dict) else None
            if newest_id:
                return newest_id
        return None

    def _process_query(self, query: str, options: dict) -> dict:
        """Fetch one query incrementally and persist its JSON envelope.

        Recovers the query's ``since_id`` and calls the X v2 search endpoint,
        which writes the ``{query, options, results, …}`` envelope to object
        storage. Runs in its own worker thread.
        """
        since_id = self.get_since_id(query)
        logger.info(f"XSearchRecentTweetsWorkflow: query={query!r} since_id={since_id}")
        envelope = self.__configuration.x_integration.search_recent_tweets(
            query, since_id=since_id, **options
        )
        results = envelope.get("results") or {}
        tweets = results.get("data") or []
        newest_id = (results.get("meta") or {}).get("newest_id")
        file_path = envelope.get("file_path")

        return {
            "query": query,
            "since_id": since_id,
            "new_count": len(tweets),
            "newest_id": newest_id,
            "file_path": file_path,
            "tweets": tweets,
        }

    def run(self, parameters: XSearchRecentTweetsWorkflowParameters) -> dict:
        if not isinstance(parameters, XSearchRecentTweetsWorkflowParameters):
            raise ValueError(
                "Parameters must be of type XSearchRecentTweetsWorkflowParameters"
            )

        options: dict = parameters.options or {}
        unknown = set(options) - _SEARCH_OPTION_KEYS
        if unknown:
            raise ValueError(
                f"Unknown options for search_recent_tweets: {sorted(unknown)}. "
                f"Accepted keys: {sorted(_SEARCH_OPTION_KEYS)} "
                "('since_id' is derived per query and cannot be set here)."
            )

        queries = parameters.queries
        if not queries:
            return {"total_new_tweets": 0, "results": []}

        # One worker thread per query, as requested — each thread fetches its
        # query independently. ``ThreadPoolExecutor.map`` preserves input order,
        # so ``results`` lines up with ``queries``.
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            results = list(
                executor.map(
                    lambda query: self._process_query(query, options),
                    queries,
                )
            )

        total_new = sum(item["new_count"] for item in results)
        return {
            "total_new_tweets": total_new,
            "results": results,
        }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_search_recent_tweets_incremental",
                description=(
                    "Run one or more X v2 recent-search queries incrementally, "
                    "in parallel (one worker thread per query). Each query is "
                    "resumed from the highest tweet id already stored for it "
                    "(since_id), so only tweets newer than the previous run are "
                    "returned. Returns, per query, the new tweets, the next "
                    "cursor (newest_id) and the persisted envelope file_path."
                ),
                func=lambda **kwargs: self.run(
                    XSearchRecentTweetsWorkflowParameters(**kwargs)
                ),
                args_schema=XSearchRecentTweetsWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
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
    """Command-line entry point for XSearchRecentTweetsWorkflow.

    Every argument has a default, so the workflow runs with no flags:

    ```
    abi dev up
    OXIGRAPH_URL=http://127.0.0.1:8432 uv run python \
        libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows/XSearchRecentTweetsWorkflow.py
    ```

    Override any of them, e.g.:

    ```
    ... XSearchRecentTweetsWorkflow.py \
        --queries '("FIFA World Cup") lang:en -is:retweet' \
        --max-results 50 --sort-order relevancy --no-persist
    ```
    """
    import argparse

    from naas_abi_core.engine.Engine import Engine

    parser = argparse.ArgumentParser(
        description=(
            "Run one or more X v2 recent-search queries incrementally and map "
            "the results into the knowledge graph."
        )
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=[
            "(FIFA World Cup) has:media lang:en -is:retweet",
        ],
        help="One or more X v2 search queries to run incrementally.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Tweets per page requested from X (10-100). Default: 100.",
    )
    parser.add_argument(
        "--sort-order",
        default="recency",
        choices=["recency", "relevancy"],
        help="Order results are returned in. Default: recency.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Max pages to fetch per query. Default: None (exhaust all new tweets).",
    )
    from datetime import datetime, timedelta, timezone

    _default_start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    parser.add_argument(
        "--start-time",
        default=_default_start_time,
        help="Oldest UTC timestamp (YYYY-MM-DDTHH:mm:ssZ), inclusive. "
        "Defaults to 24 hours before script start time if unset.",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="Newest UTC timestamp (ISO 8601) to search to. Default: None.",
    )
    parser.add_argument(
        "--until-id",
        default=None,
        help="Return tweets older than this tweet id. Default: None.",
    )
    parser.add_argument(
        "--persist",
        dest="persist",
        action="store_true",
        default=True,
        help="Insert the generated tweet graph into the triple store (default).",
    )
    parser.add_argument(
        "--no-persist",
        dest="persist",
        action="store_false",
        help="Fetch and graph without writing to the triple store.",
    )
    args = parser.parse_args()

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.x"])

    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegrationConfiguration,
    )

    bearer_token = engine.services.secret.get("X_BEARER_TOKEN")
    datastore_path = ABIModule.get_instance().configuration.datastore_path

    x_integration = XIntegration(
        XIntegrationConfiguration(
            bearer_token=bearer_token, datastore_path=datastore_path
        )
    )

    workflow = XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=engine.services.object_storage,
            datastore_path=datastore_path,
        )
    )

    # Only forward options the user actually set, so unset ones keep the X API
    # defaults rather than being sent as null.
    options: dict = {
        "max_results": args.max_results,
        "sort_order": args.sort_order,
        "max_pages": args.max_pages,
    }
    if args.start_time is not None:
        options["start_time"] = args.start_time
    if args.end_time is not None:
        options["end_time"] = args.end_time
    if args.until_id is not None:
        options["until_id"] = args.until_id

    output = workflow.run(
        XSearchRecentTweetsWorkflowParameters(
            queries=args.queries,
            options=options,
            persist=args.persist,
        )
    )

    for item in output["results"]:
        cursor = item["since_id"] or "none (first run)"
        print(
            f"[{item['query'][:60]}…] since_id={cursor} → "
            f"{item['new_count']} new tweets"
        )
        if item["newest_id"]:
            print(f"  Next since_id: {item['newest_id']}")

    print(f"Total new tweets: {output['total_new_tweets']}")
