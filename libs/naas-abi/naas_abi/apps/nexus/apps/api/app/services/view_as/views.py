"""A view as the JSON the web reads (the answer of ``POST /api/iam/view-as``, and the
``view`` of ``GET /api/auth/oidc/session``)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.view_as.port import ViewRecord, WorkspaceRef


def iso(value: datetime) -> str:
    """Times are kept as naive UTC."""
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def view_json(record: ViewRecord) -> dict[str, Any]:
    return {
        "person": {"id": record.person_principal_id, "name": record.person_name},
        "workspace": {"id": record.workspace_id, "name": record.workspace_name},
        "ends_at": iso(record.ends_at),
        # When the identity provider groups were recorded (the person's most recent
        # sign-in session); null for a person who never signed in: stored groups only.
        "groups_from": iso(record.groups_from) if record.groups_from else None,
    }


def workspace_json(workspace: WorkspaceRef) -> dict[str, Any]:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "organization": (
            {"id": workspace.organization_id, "name": workspace.organization_name}
            if workspace.organization_id
            else None
        ),
    }
