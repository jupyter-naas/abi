"""The runtime an open Documents, Sheets or Slides project is bound to.

Each project has one label per workspace (``<kind>/<workspace>/<slug>``) and a
legacy one (``<kind>/<slug>``); the first label given is the preferred one.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.coding_environment.port import (
    CodingEnvironmentRecord,
    CodingEnvironmentStorePort,
)


async def bindings_for(
    store: CodingEnvironmentStorePort, *, workspace_id: str, user_id: str, labels: list[str]
) -> list[CodingEnvironmentRecord]:
    """The user's environments bound to one of ``labels``, the preferred label first."""
    rows = await store.find_by_labels(workspace_id=workspace_id, user_id=user_id, labels=labels)
    preferred = labels[0] if labels else None
    rows.sort(key=lambda row: 0 if row.label == preferred else 1)
    return rows


async def sidecar_for(
    store: CodingEnvironmentStorePort, *, workspace_id: str, user_id: str, labels: list[str]
) -> tuple[str | None, str | None]:
    """``(sidecar_base, sidecar_secret)`` of the first binding that has both."""
    for row in await bindings_for(store, workspace_id=workspace_id, user_id=user_id, labels=labels):
        if row.sidecar_base and row.sidecar_secret:
            return str(row.sidecar_base), str(row.sidecar_secret)
    return None, None
