"""Event class for the frontend analytics tracker.

One published event per raw tracker event, so the analytics write path uses the
durable EventService log instead of one object-storage PUT per event.

The tracker's payload is ``extra="allow"`` (any property the frontend chooses
to send), while ``RDFEntity`` is ``extra="forbid"``. The full payload therefore
travels verbatim in ``payload_json`` and is what the read path hands back; the
columns beside it are a projection of the same data, declared so the filter DSL
can push predicates down to SQL instead of loading the log into Python.
"""

from __future__ import annotations

import datetime
from typing import Annotated, ClassVar

from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from pydantic import Field

NAMESPACE = "http://ontology.naas.ai/abi/nexus/analytics/"


class AnalyticsEventRecorded(LogProcess):
    """AnalyticsEventRecorded"""

    _class_uri: ClassVar[str] = f"{NAMESPACE}AnalyticsEventRecorded"
    _name: ClassVar[str] = "AnalyticsEventRecorded"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "event_id": f"{NAMESPACE}eventId",
        "event_name": f"{NAMESPACE}eventName",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "page_path": f"{NAMESPACE}pagePath",
        "payload_json": f"{NAMESPACE}payloadJson",
        "session_id": f"{NAMESPACE}sessionId",
        "timestamp": f"{NAMESPACE}timestamp",
        "user_email": f"{NAMESPACE}userEmail",
        "user_id": f"{NAMESPACE}userId",
        "workspace_id": f"{NAMESPACE}workspaceId",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    event_id: Annotated[str, Field(description="Tracker-assigned id for this event.")] | None = None
    timestamp: (
        Annotated[str, Field(description="ISO 8601 instant the tracker recorded, as sent.")] | None
    ) = None
    event_name: (
        Annotated[str, Field(description="Tracker event name, e.g. page_viewed.")] | None
    ) = None
    user_id: (
        Annotated[str, Field(description="Identifier of the user the event belongs to.")] | None
    ) = None
    user_email: (
        Annotated[str, Field(description="Email of the user the event belongs to.")] | None
    ) = None
    workspace_id: Annotated[str, Field(description="Workspace the event occurred in.")] | None = (
        None
    )
    session_id: (
        Annotated[str, Field(description="Tracker session the event belongs to.")] | None
    ) = None
    page_path: (
        Annotated[str, Field(description="Path of the page the event occurred on.")] | None
    ) = None
    payload_json: (
        Annotated[
            str,
            Field(
                description="The tracker payload verbatim, JSON-encoded. Source of truth for the read path."
            ),
        ]
        | None
    ) = None
    created_at: (
        Annotated[
            datetime.datetime,
            Field(
                description="ISO 8601 timestamp at which the event occurred. Populated by EventService.publish() if not set by the caller."
            ),
        ]
        | None
    ) = None


AnalyticsEventRecorded.model_rebuild()
