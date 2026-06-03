"""Search service domain events.

Published through `EventService.publish` like every other domain event:
- durable (SQLite-backed log) so monitoring/audit consumers can replay,
- broadcast on the bus so live subscribers (dashboards, alerters) see them.

Search owns these classes (vs. the producing service) because the failure
semantics — "I tried to index this document and could not" — belong to the
consumer that did the work, not to the upstream service whose event was
fine.

The intended consumers are MONITORING, not retry. The payload carries only
what dashboards / alert rules need (source, operation, error class, message).
If a retry use case appears later, add the original-event reference as a
separate property — don't bloat this one preemptively.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Any, ClassVar, Optional

from pydantic import Field

from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.triple_store.ontologies.modules.TripleStoreEventOntology import (
    RDFEntity,
)


_SEARCH_NS = "http://ontology.naas.ai/abi/search/"


class SearchIndexFailed(LogProcess, RDFEntity):
    """A source failed to index or remove a document.

    Emitted by an indexable source when its `index`/`remove`/`reindex` path
    raises. The source catches, publishes this event, then moves on — it
    does NOT retry. Retry, if needed, is a separate consumer subscribing to
    this event.
    """

    _class_uri: ClassVar[str] = _SEARCH_NS + "SearchIndexFailed"
    _name: ClassVar[str] = "SearchIndexFailed"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "source": _SEARCH_NS + "source",
        "operation": _SEARCH_NS + "operation",
        "document_id": _SEARCH_NS + "documentId",
        "error_type": _SEARCH_NS + "errorType",
        "error_message": _SEARCH_NS + "errorMessage",
    }
    _object_properties: ClassVar[set[str]] = set()

    source: Optional[Annotated[str, Field(description="Source name, e.g. 'graph'.")]] = None
    operation: Optional[
        Annotated[str, Field(description="'index' | 'remove' | 'reindex'.")]
    ] = None
    document_id: Optional[
        Annotated[
            str,
            Field(
                description="Document ID that failed. None when failure happened before a Document could be built (e.g. projection error)."
            ),
        ]
    ] = None
    error_type: Optional[
        Annotated[str, Field(description="Exception class name.")]
    ] = None
    error_message: Optional[
        Annotated[str, Field(description="Exception message; truncate at the source.")]
    ] = None
    created_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="ISO 8601 timestamp at which the event occurred. Populated by EventService.publish() if not set by the caller."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[datetime.datetime, Field(description="Date of creation of the resource.")]
    ] = None
    creator: Optional[
        Annotated[Any, Field(description="An entity responsible for making the resource.")]
    ] = None


class DocumentIndexed(LogProcess, RDFEntity):
    """One document was written to a source's index.

    Pairs with SearchIndexFailed so dashboards can compute failure RATE
    (failed / (indexed + failed)) rather than just absolute failure counts.
    """

    _class_uri: ClassVar[str] = _SEARCH_NS + "DocumentIndexed"
    _name: ClassVar[str] = "DocumentIndexed"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "source": _SEARCH_NS + "source",
        "document_id": _SEARCH_NS + "documentId",
    }
    _object_properties: ClassVar[set[str]] = set()

    source: Optional[Annotated[str, Field(description="Source name.")]] = None
    document_id: Optional[Annotated[str, Field(description="Document ID written.")]] = None
    created_at: Optional[
        Annotated[datetime.datetime, Field(description="ISO 8601 timestamp.")]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[datetime.datetime, Field(description="Date of creation of the resource.")]
    ] = None
    creator: Optional[
        Annotated[Any, Field(description="An entity responsible for making the resource.")]
    ] = None


class DocumentRemoved(LogProcess, RDFEntity):
    """One document was removed from a source's index."""

    _class_uri: ClassVar[str] = _SEARCH_NS + "DocumentRemoved"
    _name: ClassVar[str] = "DocumentRemoved"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "source": _SEARCH_NS + "source",
        "document_id": _SEARCH_NS + "documentId",
    }
    _object_properties: ClassVar[set[str]] = set()

    source: Optional[Annotated[str, Field(description="Source name.")]] = None
    document_id: Optional[Annotated[str, Field(description="Document ID removed.")]] = None
    created_at: Optional[
        Annotated[datetime.datetime, Field(description="ISO 8601 timestamp.")]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[datetime.datetime, Field(description="Date of creation of the resource.")]
    ] = None
    creator: Optional[
        Annotated[Any, Field(description="An entity responsible for making the resource.")]
    ] = None


class IndexRebuilt(LogProcess, RDFEntity):
    """A source completed a full reindex.

    Useful as a heartbeat for "is my recovery path actually working" and to
    correlate index size jumps with deploys.
    """

    _class_uri: ClassVar[str] = _SEARCH_NS + "IndexRebuilt"
    _name: ClassVar[str] = "IndexRebuilt"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "source": _SEARCH_NS + "source",
        "document_count": _SEARCH_NS + "documentCount",
        "duration_ms": _SEARCH_NS + "durationMs",
    }
    _object_properties: ClassVar[set[str]] = set()

    source: Optional[Annotated[str, Field(description="Source name.")]] = None
    document_count: Optional[
        Annotated[int, Field(description="Number of documents written during the reindex.")]
    ] = None
    duration_ms: Optional[
        Annotated[float, Field(description="Wall-clock duration of the reindex.")]
    ] = None
    created_at: Optional[
        Annotated[datetime.datetime, Field(description="ISO 8601 timestamp.")]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[datetime.datetime, Field(description="Date of creation of the resource.")]
    ] = None
    creator: Optional[
        Annotated[Any, Field(description="An entity responsible for making the resource.")]
    ] = None
