"""Ports + value types for the federated SearchService.

The shape:
- A `Document` is the generic unit an indexable source stores. Non-RDF on
  purpose, so the same service can index triples, files, chat history, etc.
- A `SearchHit` is what a source returns when queried. The core fields
  (`title`, `snippet`, `url`, `kind`) are what a frontend renders by default;
  source-specific extras go in `metadata`.
- A `SearchEvent` is a streaming envelope. `SearchService.search` yields these
  in real time so callers (e.g. an SSE endpoint) can render results as each
  source produces them rather than waiting for all sources to finish.
- `ISearchSource` is the per-backend port. Live-query sources (DuckDuckGo,
  a SPARQL passthrough) leave `supports_indexing()` False and never see
  `index/remove/reindex`. Indexable sources implement those and typically
  subscribe to upstream domain events to keep their index current.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Union


@dataclass(frozen=True)
class Document:
    """The unit an indexable source stores.

    `fields` is the searchable payload (free text, labels, tags). `metadata`
    is anything the source wants to round-trip back into `SearchHit.metadata`
    without touching the index logic — e.g. the originating graph name, MIME
    type, parent folder.
    """

    id: str
    fields: dict[str, Union[str, list[str]]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    """One result returned by a source.

    `id` is unique within `source`; `(source, id)` is the global dedup key.
    `score` is per-source — do NOT compare across sources directly; the
    federator returns hits grouped by source for that reason.
    """

    id: str
    source: str
    kind: str
    title: str
    snippet: str
    score: float
    url: str | None = None
    highlights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Streaming envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchStarted:
    query: str
    sources: list[str]


@dataclass(frozen=True)
class SourceStarted:
    source: str


@dataclass(frozen=True)
class Hit:
    hit: SearchHit


@dataclass(frozen=True)
class SourceFinished:
    source: str
    count: int
    duration_ms: float


@dataclass(frozen=True)
class SourceError:
    source: str
    error_type: str
    error_message: str
    duration_ms: float


@dataclass(frozen=True)
class SearchFinished:
    total_hits: int
    duration_ms: float


SearchEvent = Union[
    SearchStarted, SourceStarted, Hit, SourceFinished, SourceError, SearchFinished
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class Exceptions:
    class SourceNotFoundError(Exception):
        pass

    class SourceAlreadyRegisteredError(Exception):
        pass

    class IndexingNotSupportedError(Exception):
        """Raised when index/remove/reindex is called on a read-only source."""


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


class ISearchSource(ABC):
    """One backend (graph, object storage, DuckDuckGo, vector index, ...).

    Querying is mandatory; indexing is opt-in. Sources that maintain their
    own index (vector, lexical) override `supports_indexing()` and implement
    `index`, `remove`, `reindex`. Live-query sources only implement `search`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier used in `SearchHit.source` and source selection."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> Iterator[SearchHit]:
        """Yield hits as they are produced.

        Yielding lazily lets the federator stream results to the caller
        without buffering whole result sets.
        """

    def supports_indexing(self) -> bool:
        return False

    def index(self, document: Document) -> None:
        raise Exceptions.IndexingNotSupportedError(
            f"Source '{self.name}' is read-only"
        )

    def remove(self, document_id: str) -> None:
        raise Exceptions.IndexingNotSupportedError(
            f"Source '{self.name}' is read-only"
        )

    def reindex(self) -> int:
        """Rebuild the index from the upstream source of truth.

        Returns the number of documents written. Required because event
        subscriptions only cover mutations after subscribe-time; without a
        reindex path the index drifts permanently on every restart-before-
        subscribe, schema change, or adapter swap.
        """
        raise Exceptions.IndexingNotSupportedError(
            f"Source '{self.name}' is read-only"
        )


class ISearchService(ABC):
    @abstractmethod
    def register_source(self, source: ISearchSource) -> None:
        pass

    @abstractmethod
    def list_sources(self) -> list[str]:
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        timeout: float = 10.0,
    ) -> Iterator[SearchEvent]:
        """Federate the query across `sources` (default: all registered).

        Yields a stream of events so the caller can render results as they
        arrive. One slow source does not block the others — each source runs
        with its own timeout and errors are isolated as `SourceError` events.
        """

    @abstractmethod
    def reindex(self, source_name: str) -> int:
        pass
