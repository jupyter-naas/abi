"""Generate a tweet-dump file in object storage from an X v2 search query.

The "produce side" of the file-ingestion loop. Pairs with
:class:`XFileIngestionPipeline` (the consume side) and the
``x_tweet_file_auto_ingestion_sensor`` (the auto-discovery glue).

Flow when the agent runs ``x_generate_tweet_dump_file(query, ...)``:

  1. We call ``XIntegration.search_recent_tweets(query, ...)`` — which
     paginates the X v2 endpoint internally and returns a flat list.
  2. We serialise that list as NDJSON (one tweet per line — cheap to
     stream-ingest later) and ``put_object`` it under ``x/dumps/`` with
     a human-readable, query-derived filename.
  3. ``ObjectStorageService.put_object`` publishes an ``ObjectPut`` event.
  4. ``x_tweet_file_auto_ingestion_sensor`` consumes that event via the
     bus, classifies the new key as a tweet dump, and enqueues a
     Dagster run that streams the file through
     :class:`XFileIngestionPipeline` into the graph.

So the visible side effect of this pipeline is "a file appears in
``x/dumps/``"; the invisible-but-automatic side effect is "the tweets
end up queryable in the graph a few seconds later". The agent can then
answer follow-up questions about the same query using the SPARQL tools.

We deliberately write to ``x/dumps/`` rather than the integration's
internal ``x/search_recent_tweets/<hash>.json`` cache: the cache is
opaque hash-named blobs meant for memoisation; ``x/dumps/`` is the
user-visible export surface, with filenames that say what they are.
Both paths emit ``ObjectPut`` and both get auto-ingested — sha256
dedupe in :class:`XFileIngestionPipeline` keeps re-ingestion idempotent.
"""

from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageDomain,
)
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
)
from pydantic import Field

# Match the v2 fields the file-ingestion pipeline already knows how to
# unpack — request them by default so the dump is graph-ready, not a
# {id, text}-only stub.
_DEFAULT_TWEET_FIELDS = [
    "author_id",
    "created_at",
    "public_metrics",
    "lang",
    "edit_history_tweet_ids",
]


@dataclass
class XGenerateTweetDumpPipelineConfiguration(PipelineConfiguration):
    """Wiring for :class:`XGenerateTweetDumpPipeline`.

    Attributes:
        x_integration: The XIntegration used to call X v2 at run time.
        object_storage: Where the dump file gets written. Must support
            :meth:`put_object` (every adapter does).
        output_prefix: Object-storage prefix the file lands under.
            Defaults to ``x/dumps`` — kept separate from the integration's
            internal ``x/search_recent_tweets`` cache so the auto-discovery
            sensor's UI / log output can tell the two apart at a glance.
    """

    x_integration: XIntegration
    object_storage: IObjectStorageDomain
    output_prefix: str = "x/dumps"


class XGenerateTweetDumpPipelineParameters(PipelineParameters):
    query: Annotated[
        str,
        Field(
            description=(
                "X v2 search query (1-4096 chars), e.g. "
                "'(openai OR anthropic) lang:en -is:retweet'. Same syntax "
                "as XIntegration.search_recent_tweets."
            ),
            example="(openai OR anthropic) lang:en -is:retweet",
        ),
    ]
    max_results: Annotated[
        int,
        Field(
            default=100,
            ge=10,
            le=100,
            description="Page size forwarded to X v2 (10-100).",
        ),
    ] = 100
    max_pages: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            description=(
                "Number of pages to fetch before stopping. Each page is "
                "an extra X v2 call; total tweets <= max_results * max_pages."
            ),
        ),
    ] = 1
    file_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Override the auto-generated filename. If omitted, the "
                "pipeline derives one as "
                "``<slug(query)>-<utc-iso-timestamp>.ndjson``. Must end "
                "in ``.ndjson`` (the format the pipeline writes)."
            ),
            example="climate-change-2026-06-03.ndjson",
        ),
    ] = None


class XGenerateTweetDumpPipeline(Pipeline):
    """Call X v2 search_recent_tweets, write the result to object storage."""

    __configuration: XGenerateTweetDumpPipelineConfiguration

    def __init__(self, configuration: XGenerateTweetDumpPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: XGenerateTweetDumpPipelineParameters) -> dict:  # type: ignore[override]
        if not isinstance(parameters, XGenerateTweetDumpPipelineParameters):
            raise ValueError(
                "Parameters must be of type XGenerateTweetDumpPipelineParameters"
            )

        logger.info(
            f"XGenerateTweetDumpPipeline: search_recent_tweets("
            f"query={parameters.query!r}, max_results={parameters.max_results}, "
            f"max_pages={parameters.max_pages})"
        )
        envelope = self.__configuration.x_integration.search_recent_tweets(
            parameters.query,
            max_results=parameters.max_results,
            max_pages=parameters.max_pages,
            tweet_fields=_DEFAULT_TWEET_FIELDS,
            sort_order="recency",
        )
        # search_recent_tweets returns the persisted envelope; the matched
        # tweets are under results.data.
        tweets = (envelope.get("results") or {}).get("data") or []
        logger.info(
            f"XGenerateTweetDumpPipeline: fetched {len(tweets)} tweets"
        )

        key = parameters.file_name or self._default_file_name(parameters.query)
        if not key.endswith(".ndjson"):
            raise ValueError(
                f"file_name must end in .ndjson (got {key!r}); the auto-"
                "ingestion sensor's classifier keys on the extension."
            )

        # NDJSON: one tweet per line. We use ensure_ascii=False so non-
        # latin glyphs in `text` stay readable; sort_keys=True so two
        # runs against an identical X response produce byte-identical
        # files (helpful when sha256 dedupe is the source of truth).
        content = "\n".join(
            _json.dumps(t, ensure_ascii=False, sort_keys=True) for t in tweets
        ).encode("utf-8")

        self.__configuration.object_storage.put_object(
            prefix=self.__configuration.output_prefix,
            key=key,
            content=content,
        )
        logger.info(
            f"XGenerateTweetDumpPipeline: wrote {len(tweets)} tweets to "
            f"{self.__configuration.output_prefix}/{key} "
            f"({len(content)} bytes) — ObjectPut will trigger auto-ingest"
        )

        return {
            "prefix": self.__configuration.output_prefix,
            "key": key,
            "tweet_count": len(tweets),
            "size_bytes": len(content),
        }

    # ----- Helpers --------------------------------------------------------------

    @staticmethod
    def _slugify(value: str) -> str:
        """Filename-safe slug — keep it short and ASCII so any FS / S3 likes it."""
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower()
        if len(slug) > 60:
            slug = slug[:60].rstrip("-")
        return slug or "query"

    @classmethod
    def _default_file_name(cls, query: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{cls._slugify(query)}-{ts}.ndjson"

    # ----- Framework hooks ------------------------------------------------------

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_generate_tweet_dump_file",
                description=(
                    "Run XIntegration.search_recent_tweets for the given "
                    "query and save the result as an NDJSON file in "
                    "object storage. The file's ObjectPut event triggers "
                    "x_tweet_file_auto_ingestion_sensor, which streams "
                    "the file through XFileIngestionPipeline into the "
                    "graph — so calling this tool both produces a "
                    "downloadable dataset file and (a few seconds later) "
                    "makes those tweets queryable via the X agent's "
                    "graph tools."
                ),
                func=lambda **kwargs: self.run(
                    XGenerateTweetDumpPipelineParameters(**kwargs)
                ),
                args_schema=XGenerateTweetDumpPipelineParameters,
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
