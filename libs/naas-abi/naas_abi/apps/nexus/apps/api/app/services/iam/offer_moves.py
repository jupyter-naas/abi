"""What moves into the workspaces' offers ("<W> access") is moved once, at start, and
recorded in ``iam_migrations`` once nothing failed (``search_sources_offer``,
``ontologies_offer``): a later choice of an administrator is never undone by a start."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

_MARKER_TABLE = (
    "CREATE TABLE IF NOT EXISTS iam_migrations ("
    "name VARCHAR(128) PRIMARY KEY, "
    "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
    "report TEXT)"
)


async def recorded(db: AsyncSession, name: str) -> bool:
    await db.execute(text(_MARKER_TABLE))
    found = await db.execute(text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": name})
    return found.first() is not None


async def record(db: AsyncSession, name: str, report: Mapping[str, Any]) -> None:
    try:
        await db.execute(
            text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
            {
                "n": name,
                "at": datetime.now(UTC).replace(tzinfo=None),
                "r": json.dumps(dict(report)),
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()  # another process recorded it first


async def access_policies(db: AsyncSession) -> dict[str, str]:
    """``{container: access policy id}`` of every organization and workspace Nexus
    recorded (``container_defaults``)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
        is_org_container,
        is_workspace_container,
    )

    rows = (
        await db.execute(
            text(
                "SELECT container, access_policy_id FROM container_defaults "
                "WHERE access_policy_id IS NOT NULL"
            )
        )
    ).all()
    return {
        str(c): str(p)
        for c, p in rows
        if is_org_container(str(c)) or is_workspace_container(str(c))
    }
