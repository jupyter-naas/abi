from __future__ import annotations

import datetime
from typing import Annotated, Any, ClassVar, Optional

from pydantic import Field

from naas_abi_core.services.event.ontologies.modules.EventOntology import (
    LogProcess,
    RDFEntity,
)

_NS = "http://ontology.naas.ai/abi/coding_environment/"


def _common_uris(extra: dict[str, str]) -> dict[str, str]:
    base = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    base.update(extra)
    return base


class _CodingEnvironmentEvent(LogProcess, RDFEntity):
    """Shared data properties for all coding-environment events."""

    created_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="ISO 8601 timestamp at which the event occurred. "
                "Populated by EventService.publish() if not set by the caller."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None


class WorkspaceProvisioned(_CodingEnvironmentEvent):
    """A workspace was created from a template."""

    _class_uri: ClassVar[str] = f"{_NS}WorkspaceProvisioned"
    _name: ClassVar[str] = "WorkspaceProvisioned"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "user": f"{_NS}user",
            "workspace_id": f"{_NS}workspaceId",
            "workspace_name": f"{_NS}workspaceName",
            "template_id": f"{_NS}templateId",
            "phase": f"{_NS}phase",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    user: Optional[Annotated[str, Field(description="Owner user id.")]] = None
    workspace_id: Optional[
        Annotated[str, Field(description="Provisioned workspace id.")]
    ] = None
    workspace_name: Optional[
        Annotated[str, Field(description="Workspace name.")]
    ] = None
    template_id: Optional[
        Annotated[str, Field(description="Template the workspace was created from.")]
    ] = None
    phase: Optional[
        Annotated[str, Field(description="Normalized lifecycle phase.")]
    ] = None


class WorkspaceStarted(_CodingEnvironmentEvent):
    """A workspace build with transition=start was issued."""

    _class_uri: ClassVar[str] = f"{_NS}WorkspaceStarted"
    _name: ClassVar[str] = "WorkspaceStarted"
    _property_uris: ClassVar[dict] = _common_uris(
        {"workspace_id": f"{_NS}workspaceId", "phase": f"{_NS}phase"}
    )
    _object_properties: ClassVar[set[str]] = set()

    workspace_id: Optional[
        Annotated[str, Field(description="Workspace id.")]
    ] = None
    phase: Optional[
        Annotated[str, Field(description="Normalized lifecycle phase.")]
    ] = None


class WorkspaceStopped(_CodingEnvironmentEvent):
    """A workspace build with transition=stop was issued."""

    _class_uri: ClassVar[str] = f"{_NS}WorkspaceStopped"
    _name: ClassVar[str] = "WorkspaceStopped"
    _property_uris: ClassVar[dict] = _common_uris(
        {"workspace_id": f"{_NS}workspaceId", "phase": f"{_NS}phase"}
    )
    _object_properties: ClassVar[set[str]] = set()

    workspace_id: Optional[
        Annotated[str, Field(description="Workspace id.")]
    ] = None
    phase: Optional[
        Annotated[str, Field(description="Normalized lifecycle phase.")]
    ] = None


class WorkspaceDeleted(_CodingEnvironmentEvent):
    """A workspace build with transition=delete was issued."""

    _class_uri: ClassVar[str] = f"{_NS}WorkspaceDeleted"
    _name: ClassVar[str] = "WorkspaceDeleted"
    _property_uris: ClassVar[dict] = _common_uris(
        {"workspace_id": f"{_NS}workspaceId"}
    )
    _object_properties: ClassVar[set[str]] = set()

    workspace_id: Optional[
        Annotated[str, Field(description="Workspace id.")]
    ] = None


class WorkspaceAccessGranted(_CodingEnvironmentEvent):
    """A scoped per-user token + embeddable app URL was minted."""

    _class_uri: ClassVar[str] = f"{_NS}WorkspaceAccessGranted"
    _name: ClassVar[str] = "WorkspaceAccessGranted"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "user": f"{_NS}user",
            "workspace_id": f"{_NS}workspaceId",
            "app_slug": f"{_NS}appSlug",
            "token_expires_at": f"{_NS}tokenExpiresAt",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    user: Optional[Annotated[str, Field(description="User access was granted to.")]] = None
    workspace_id: Optional[
        Annotated[str, Field(description="Workspace id.")]
    ] = None
    app_slug: Optional[
        Annotated[str, Field(description="App slug the access targets.")]
    ] = None
    token_expires_at: Optional[
        Annotated[str, Field(description="Token expiry, if known.")]
    ] = None


class WorkspaceProvisionFailed(_CodingEnvironmentEvent):
    """A provision attempt failed."""

    _class_uri: ClassVar[str] = f"{_NS}WorkspaceProvisionFailed"
    _name: ClassVar[str] = "WorkspaceProvisionFailed"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "user": f"{_NS}user",
            "workspace_id": f"{_NS}workspaceId",
            "message": f"{_NS}message",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    user: Optional[Annotated[str, Field(description="Owner user id.")]] = None
    workspace_id: Optional[
        Annotated[
            str,
            Field(
                description="Workspace id if known, else the requested workspace name."
            ),
        ]
    ] = None
    message: Optional[
        Annotated[str, Field(description="String representation of the error.")]
    ] = None


# Rebuild models to resolve forward references
WorkspaceProvisioned.model_rebuild()
WorkspaceStarted.model_rebuild()
WorkspaceStopped.model_rebuild()
WorkspaceDeleted.model_rebuild()
WorkspaceAccessGranted.model_rebuild()
WorkspaceProvisionFailed.model_rebuild()
