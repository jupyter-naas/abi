"""Typed inputs and outputs of the X workflows.

Plain pydantic models with no module import, so the module class can declare its
workflows with them without a circular import.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DEFAULT_ENVELOPE_PREFIX = "x/search_recent_tweets"
# Envelope paths of one reprocess run travel through a journaled step, whose result
# is at most 256 KiB: a run takes this many (default: DEFAULT_REPROCESS_ENVELOPES).
MAX_REPROCESS_ENVELOPES = 1500
DEFAULT_REPROCESS_ENVELOPES = 1000


class SearchRecentTweetsInput(BaseModel):
    filter: str = Field(
        description="Name of a `search_recent_tweets_workflow` entry of the module config."
    )


class SearchRecentTweetsOutput(BaseModel):
    filter: str
    envelopes: int = Field(description="Envelopes this run saved to object storage.")
    new_tweets: int = 0
    mapped: int = Field(
        default=0, description="Envelopes the mapping runs put into the graph."
    )
    counts_followed: bool = False
    dataset: dict[str, Any] | None = None
    app: dict[str, Any] | None = None


class MapTweetEnvelopeInput(BaseModel):
    path: str = Field(description="Object-storage path of a search envelope.")
    persist: bool = Field(
        default=True, description="Persist the mapped triples to the triple store."
    )
    force: bool = Field(
        default=False,
        description="Map even when the envelope is already in the graph and the dataset.",
    )
    graph_name: str | None = Field(
        default=None, description="Named graph IRI (module config default)."
    )


class MapTweetEnvelopeOutput(BaseModel):
    path: str
    status: Literal["mapped", "dataset_only"] = Field(
        description=(
            "`mapped`: the pipeline ran. `dataset_only`: the graph already had the "
            "envelope; only the dataset still needs it."
        )
    )


class ReprocessTweetEnvelopesInput(BaseModel):
    prefix: str = Field(
        default=DEFAULT_ENVELOPE_PREFIX,
        description="Object-storage folder swept recursively for search envelopes.",
    )
    persist: bool = True
    force: bool = Field(
        default=False,
        description="Re-map every envelope, also those already in the graph and the dataset.",
    )
    max_age_hours: int | None = Field(
        default=None,
        ge=1,
        description="Only envelopes whose filename timestamp is within the last N hours.",
    )
    max_envelopes: int = Field(
        default=DEFAULT_REPROCESS_ENVELOPES,
        ge=1,
        le=MAX_REPROCESS_ENVELOPES,
        description=(
            "Envelopes one run takes (those to map first, then those the dataset lacks); "
            "launch it again for the rest of a large folder."
        ),
    )
    app_publish: bool = Field(
        default=False,
        description="Republish the Recent Tweets app when at least one envelope was mapped.",
    )


class ReprocessTweetEnvelopesOutput(BaseModel):
    prefix: str
    listed: int
    mapped: int
    skipped: int = Field(description="Envelopes already in the graph and the dataset.")
    dataset_only: int = 0
    truncated: bool = False
    dataset: dict[str, Any] | None = None
    app: dict[str, Any] | None = None


class CountRecentTweetsInput(BaseModel):
    query: str = Field(
        description="X v2 search query whose recent-post count to follow."
    )


class CountRecentTweetsOutput(BaseModel):
    query: str
    buckets: int
    mapped: int
    partial_mapped: int
    dataset_sync: dict[str, Any] | None = None
