import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
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
        datastore_path: Object-storage prefix under which the integration writes
            ``search_recent_tweets/<slug>/<timestamp>_<slug>.json`` files.
    """

    x_integration: XIntegration
    object_storage: ObjectStorageService
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
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


class XSearchRecentTweetsWorkflow(Workflow[XSearchRecentTweetsWorkflowParameters]):
    """Run several X recent-search queries incrementally.

    For every query the workflow recovers a ``since_id`` from the datastore (the
    highest tweet id seen on a previous run) and asks X only for newer tweets.
    The integration persists each response, so the cursor advances on its own:
    the first run fetches the last 7 days, and every subsequent run returns only
    what appeared since. ``since_id`` is read by scanning the per-query folder
    newest-to-oldest and taking the first ``results.meta.newest_id`` found, so a
    run that returned zero new tweets (no ``newest_id``) does not reset it.
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

        results: list[dict] = []
        total_new = 0
        for query in parameters.queries:
            since_id = self.get_since_id(query)
            logger.info(
                f"XSearchRecentTweetsWorkflow: query={query!r} since_id={since_id}"
            )
            response = self.__configuration.x_integration.search_recent_tweets(
                query, since_id=since_id, **options
            )
            tweets = response.get("data") or []
            newest_id = (response.get("meta") or {}).get("newest_id")
            total_new += len(tweets)
            results.append(
                {
                    "query": query,
                    "since_id": since_id,
                    "new_count": len(tweets),
                    "newest_id": newest_id,
                    "tweets": tweets,
                }
            )

        return {"total_new_tweets": total_new, "results": results}

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_search_recent_tweets_incremental",
                description=(
                    "Run one or more X v2 recent-search queries incrementally. "
                    "Each query is resumed from the highest tweet id already "
                    "stored for it (since_id), so only tweets newer than the "
                    "previous run are returned. Returns the new tweets per query "
                    "plus the next cursor (newest_id)."
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
