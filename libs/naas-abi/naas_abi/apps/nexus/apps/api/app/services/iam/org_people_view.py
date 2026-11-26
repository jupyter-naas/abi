"""An organization's people see it, and nothing it holds, once (``org_people_view_v1``).

An earlier version gave "<O> people" ``builtin.viewer`` and "Viewer access" at
``${my workspaces}``: its people (the organization's admins, and whoever holds a role at
the organization itself) listed its secrets and read whatever it holds (Organization
Files, its drive, its graphs, its datasets), and a Member wrote its Organization Files
through the built-in role of their level. Now the organization is ``no_membership_roles``
(Nexus catalog 21: no built-in role attached at ``${my workspaces}`` gives anything
there), and "<O> people" holds "Organization view" (``levels.ORG_VIEW``: see it, list it)
at ``${my workspaces}`` and at the organization, its bound
(``container_defaults.group_attachments``).

For each organization Nexus records, the move detaches the two policies of before from
its "<O> people" and attaches "Organization view" twice. Its admins keep what
``builtin.admin`` attached at the organization gives them ("<O> admins"); someone it
should still give Organization Files is given them by a policy attached at the
organization (a group's, or theirs). Recorded in ``iam_migrations`` once nothing failed.
As ``api``. Idempotent.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import offer_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import LEVELS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import is_org_container
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.names import MY_CONTAINERS_SCOPE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "org_people_view_v1"


@dataclass
class Report:
    # Organizations whose "<O> people" changed.
    converted: list[str] = field(default_factory=list)
    detached: int = 0
    attached: int = 0
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "converted": sorted(self.converted),
            "detached": self.detached,
            "attached": self.attached,
            "failed": dict(sorted(self.failed.items())),
        }


def apply(iam: Any, people: Mapping[str, str]) -> Report:
    """``people``: ``{organization container: its "<O> people" group id}``. As ``api``."""
    report = Report()
    with as_service_account("api"):
        levels = LEVELS.get(iam)
        before = {(roles.VIEWER, MY_CONTAINERS_SCOPE), (levels.viewer_access, MY_CONTAINERS_SCOPE)}
        for container, group_id in sorted(people.items()):
            wanted = {(levels.org_view, MY_CONTAINERS_SCOPE), (levels.org_view, container)}
            try:
                if iam.get_group(group_id).membership_of != container:
                    continue  # recorded before #1585: its roles are attachments still
                held = {(a.policy_id, a.scope) for a in iam.list_attachments(principal_id=group_id)}
                changed = False
                # Attached first: a failure in between leaves the view, never nothing.
                for policy_id, scope in sorted(wanted - held, key=str):
                    iam.attach_policy(policy_id, group_id, scope)
                    report.attached += 1
                    changed = True
                for policy_id, scope in sorted(before & held, key=str):
                    iam.detach_policy(policy_id, group_id, scope)
                    report.detached += 1
                    changed = True
                if changed:
                    report.converted.append(container)
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[container] = str(exc)
    return report


async def org_people(db: AsyncSession) -> dict[str, str]:
    """``{organization container: "<O> people" group id}`` of every organization Nexus
    recorded (``container_defaults``)."""
    rows = (
        await db.execute(
            text(
                "SELECT container, members_group_id FROM container_defaults "
                "WHERE members_group_id IS NOT NULL"
            )
        )
    ).all()
    return {str(c): str(g) for c, g in rows if is_org_container(str(c))}


async def migrate(db: AsyncSession, iam: Any) -> Report | None:
    """Once: each organization's people see it, and nothing it holds. None when
    recorded."""
    if await offer_moves.recorded(db, MIGRATION_NAME):
        return None
    people = await org_people(db)
    report = await run_in_threadpool(apply, iam, people)
    if report.failed:
        logger.warning(
            "Organization view: %d organizations not converted yet (next start): %s",
            len(report.failed),
            report.failed,
        )
        return report
    await offer_moves.record(db, MIGRATION_NAME, report.to_dict())
    logger.info("Organization view: %s", report.to_dict())
    return report


__all__ = ["MIGRATION_NAME", "Report", "apply", "migrate", "org_people"]
