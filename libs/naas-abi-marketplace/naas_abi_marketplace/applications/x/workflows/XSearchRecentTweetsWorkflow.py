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
from naas_abi_marketplace.applications.x.pipelines.XSearchRecentTweetsPipeline import (
    XSearchRecentTweetsPipeline,
    XSearchRecentTweetsPipelineConfiguration,
    XSearchRecentTweetsPipelineParameters,
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
        triple_store: Service the per-query XSearchRecentTweetsPipeline uses to
            dedup against and persist the generated tweet graph. Defaults to the
            engine's triple store so callers don't have to wire it explicitly.
        datastore_path: Object-storage prefix under which the integration writes
            ``search_recent_tweets/<slug>/<timestamp>_<slug>.json`` files.
        graph_name: Named graph the pipeline writes the tweet triples into.
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
    """Run several X recent-search queries incrementally and graph the results.

    For every query the workflow recovers a ``since_id`` from the datastore (the
    highest tweet id seen on a previous run) and asks X only for newer tweets.
    The integration persists each response, so the cursor advances on its own:
    the first run fetches the last 7 days, and every subsequent run returns only
    what appeared since. ``since_id`` is read by scanning the per-query folder
    newest-to-oldest and taking the first ``results.meta.newest_id`` found, so a
    run that returned zero new tweets (no ``newest_id``) does not reset it.

    Each query is then handed to :class:`XSearchRecentTweetsPipeline` via the
    ``file_path`` of the JSON envelope the integration just persisted, which maps
    the tweets / users / media into the knowledge graph and (when ``persist`` is
    set) inserts them into the configured named graph. Queries are processed
    concurrently, one worker thread per query, so a batch of N queries runs its N
    fetch+map passes in parallel.
    """

    __configuration: XSearchRecentTweetsWorkflowConfiguration
    __storage_utils: StorageUtils
    __pipeline: XSearchRecentTweetsPipeline

    def __init__(self, configuration: XSearchRecentTweetsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)
        # One pipeline drives every query: it holds no per-query mutable state
        # (each run() builds its own graph + dedup cache), so it is safe to call
        # concurrently from the worker threads below.
        self.__pipeline = XSearchRecentTweetsPipeline(
            XSearchRecentTweetsPipelineConfiguration(
                x_integration=self.__configuration.x_integration,
                triple_store=self.__configuration.triple_store,
                object_storage=self.__configuration.object_storage,
                graph_name=self.__configuration.graph_name,
                datastore_path=self.__configuration.datastore_path,
            )
        )

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

    def _process_query(
        self, query: str, options: dict, persist: bool
    ) -> dict:
        """Fetch one query incrementally, persist it, and graph it.

        Recovers the query's ``since_id``, calls the X v2 search endpoint (which
        writes the ``{query, options, results, …}`` envelope to object storage),
        then feeds that envelope's ``file_path`` straight to
        :class:`XSearchRecentTweetsPipeline` to map and (optionally) persist the
        tweets / users / media. Runs in its own worker thread.
        """
        since_id = self.get_since_id(query)
        logger.info(
            f"XSearchRecentTweetsWorkflow: query={query!r} since_id={since_id}"
        )
        envelope = self.__configuration.x_integration.search_recent_tweets(
            query, since_id=since_id, **options
        )
        results = envelope.get("results") or {}
        tweets = results.get("data") or []
        newest_id = (results.get("meta") or {}).get("newest_id")
        file_path = envelope.get("file_path")

        triples = 0
        if file_path:
            graph = self.__pipeline.run(
                XSearchRecentTweetsPipelineParameters(
                    file_path=file_path,
                    options={},  # ignored when file_path is set (read from file)
                    persist=persist,
                )
            )
            triples = len(graph)
        else:
            logger.warning(
                f"XSearchRecentTweetsWorkflow: query={query!r} returned no "
                "envelope file_path; skipping graph mapping for this query."
            )

        return {
            "query": query,
            "since_id": since_id,
            "new_count": len(tweets),
            "newest_id": newest_id,
            "file_path": file_path,
            "triples": triples,
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
            return {"total_new_tweets": 0, "total_triples": 0, "results": []}

        # One worker thread per query, as requested — each thread fetches its
        # query and runs the pipeline independently. ``ThreadPoolExecutor.map``
        # preserves input order, so ``results`` lines up with ``queries``.
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            results = list(
                executor.map(
                    lambda query: self._process_query(
                        query, options, parameters.persist
                    ),
                    queries,
                )
            )

        total_new = sum(item["new_count"] for item in results)
        total_triples = sum(item["triples"] for item in results)
        return {
            "total_new_tweets": total_new,
            "total_triples": total_triples,
            "results": results,
        }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_search_recent_tweets_incremental",
                description=(
                    "Run one or more X v2 recent-search queries incrementally, "
                    "in parallel (one worker thread per query), and map each "
                    "result into the knowledge graph. Each query is resumed from "
                    "the highest tweet id already stored for it (since_id), so "
                    "only tweets newer than the previous run are returned and "
                    "ingested. Returns, per query, the new tweets, the next "
                    "cursor (newest_id), the persisted envelope file_path and the "
                    "number of triples added."
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
