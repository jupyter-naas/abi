"""Platform Files moves into the offer, once (``files_offer_v1``; ADR
``20261125_offer_gives_outside_resources``, decision 5).

An earlier version gave Platform Files to a workspace's people through a platform group
per workspace, "Platform Files · <W> (<workspace id>)", holding one of two platform
policies, "Platform Files · read" or "Platform Files · write", its members kept equal to
W's people by Nexus (#1590). The offer now says it: the ``GivenPlatformFiles`` section of
"<W> access" (``given_files``), which IAM gives to W's people while they belong to W.

For each such group, the mode it held becomes ``GivenPlatformFiles`` in its workspace's
"<W> access" (the wider mode, should the section be there already); the group is then
deleted, and the two policies once nothing else holds them (one attached by hand is kept
and named). A group of a workspace Nexus no longer records is deleted. Recorded in
``iam_migrations`` once nothing failed. As ``api``.

Also here, the legacy drive flags (#1529, #1587): ``0073_drop_drive_flags.sql`` kept the
flagged workspaces in ``workspace_drive_flags_legacy`` (PostgreSQL). The access move
(``access_model_v1``) converts them: ``platform_drive_enabled`` gives the workspace's
people Platform Files, read and write (``GivenPlatformFiles``);
``system_drive_enabled`` is reported, not converted (System Files is the platform
admin's to give). Then the holding table is dropped.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.iam import given_files, offer_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.given_files import READ, WRITE, Mode
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    PLATFORM,
    is_workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import offer_of, with_offer
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, PrincipalRecord
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "files_offer_v1"

# What the earlier version wrote (#1590).
READ_POLICY = "Platform Files · read"
WRITE_POLICY = "Platform Files · write"
GROUP_PREFIX = "Platform Files · "
_GROUP_NAME = re.compile(r"^Platform Files · (?:(?P<label>.*) )?\((?P<workspace>[^()]+)\)$")

HOLDING_TABLE = "workspace_drive_flags_legacy"


def _pages(listing: Any, **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def workspace_of_group(group: PrincipalRecord) -> str | None:
    """The workspace an earlier version's Platform Files group was for, or None."""
    if group.kind != "group" or group.owner_scope != PLATFORM or group.status == "deleted":
        return None
    if getattr(group, "level_group", False) or getattr(group, "membership_of", None):
        return None
    found = _GROUP_NAME.match(group.name or "")
    return found.group("workspace") if found else None


def _workspace_containers(policies: Mapping[str, str]) -> dict[str, str]:
    return {
        workspace: container
        for container in policies
        if is_workspace_container(container) and (workspace := workspace_of(container))
    }


def give_platform_files(iam: Any, policy_id: str, mode: Mode) -> bool:
    """``GivenPlatformFiles`` in ``mode`` (or wider, as it is) in the access policy
    ``policy_id``; every other statement kept. Whether it changed. In the ambient call
    context (``api`` for the moves)."""
    policy = iam.get_policy(policy_id)
    held = offer_of(policy.document)
    wanted = replace(held, platform_files=given_files.wider(held.platform_files, mode))
    if wanted == held:
        return False
    iam.update_policy(
        policy.id, expected_revision=policy.revision, document=with_offer(policy.document, wanted)
    )
    return True


# -- the move of the groups ----------------------------------------------------------------


@dataclass
class Report:
    # Workspaces whose "<W> access" now gives Platform Files, by mode.
    written: dict[str, str] = field(default_factory=dict)
    # Workspaces that already gave it as wide.
    kept: list[str] = field(default_factory=list)
    # Groups of a workspace Nexus no longer records (deleted, nothing written).
    gone: list[str] = field(default_factory=list)
    groups_deleted: int = 0
    policies_deleted: int = 0
    # A policy someone else still holds, kept: ``{name: holders}``.
    policies_kept: dict[str, int] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "written": dict(sorted(self.written.items())),
            "kept": len(self.kept),
            "gone": sorted(self.gone),
            "groups_deleted": self.groups_deleted,
            "policies_deleted": self.policies_deleted,
            "policies_kept": self.policies_kept,
            "failed": self.failed,
        }


def _legacy_policies(iam: Any) -> dict[str, str]:
    """``{name: id}`` of the two platform policies an earlier version wrote."""
    return {
        p.name: str(p.id)
        for p in _pages(iam.list_policies)
        if p.owner_scope == PLATFORM and p.name in (READ_POLICY, WRITE_POLICY)
    }


def _mode_of(iam: Any, group_id: str, legacy: Mapping[str, str]) -> Mode | None:
    held = {a.policy_id for a in iam.list_attachments(principal_id=group_id) if a.scope is None}
    if legacy.get(WRITE_POLICY) in held:
        return WRITE
    if legacy.get(READ_POLICY) in held:
        return READ
    return None


def apply(iam: Any, policies: Mapping[str, str]) -> Report:
    """Move each Platform Files group into its workspace's access policy
    (``{container: access policy id}``), then delete the groups and the two policies.
    As ``api``. Idempotent: a second pass finds nothing."""
    report = Report()
    containers = _workspace_containers(policies)
    with as_service_account("api"):
        legacy = _legacy_policies(iam)
        groups = sorted(_pages(iam.list_groups), key=lambda g: str(g.id))
        for group in groups:
            workspace = workspace_of_group(group)
            if workspace is None:
                continue
            try:
                mode = _mode_of(iam, str(group.id), legacy)
                container = containers.get(workspace)
                if container is None:
                    report.gone.append(workspace)
                elif mode is not None:
                    if give_platform_files(iam, policies[container], mode):
                        report.written[workspace] = mode
                    else:
                        report.kept.append(workspace)
                iam.delete_group(str(group.id))
                report.groups_deleted += 1
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[workspace] = str(exc)
        if report.failed:
            return report  # the policies wait for every group
        for name, policy_id in sorted(legacy.items()):
            try:
                holders = iam.list_attachments(policy_id=policy_id)
                if holders:
                    report.policies_kept[name] = len(holders)
                    continue
                iam.delete_policy(policy_id)
                report.policies_deleted += 1
            except IAMNotFoundError:
                continue
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[name] = str(exc)
    return report


async def migrate(db: AsyncSession, iam: Any) -> Report | None:
    """Once: the Platform Files groups into the offers. None when recorded."""
    if await offer_moves.recorded(db, MIGRATION_NAME):
        return None
    policies = await offer_moves.access_policies(db)
    report = await run_in_threadpool(apply, iam, policies)
    if report.failed:
        logger.warning(
            "Platform Files: %d groups or policies not moved yet (next start): %s",
            len(report.failed),
            report.failed,
        )
        return report
    await offer_moves.record(db, MIGRATION_NAME, report.to_dict())
    if report.written:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        AUTHZ.forget_offers()
    if report.policies_kept:
        logger.warning(
            "Platform Files: kept the policies someone else holds: %s", report.policies_kept
        )
    logger.info("Platform Files in the offer: %s", report.to_dict())
    return report


# -- the legacy drive flags (#1529 dropped them, #1587 converts them) -------------------


@dataclass(frozen=True)
class DriveFlagChange:
    """One line of the conversion report of the legacy drive flags.

    ``flag``: ``"platform"`` (``platform_drive_enabled``) or ``"system"``
    (``system_drive_enabled``). ``action``: ``"converted"`` (the workspace's offer now
    gives Platform Files, read and write), ``"reported"`` (kept out on purpose: System
    Files is the platform admin's to give) or ``"none"`` (nothing to do, ``detail``
    says why)."""

    workspace_id: str
    flag: Literal["platform", "system"]
    action: Literal["converted", "reported", "none"]
    detail: str


async def _holding_rows(db: AsyncSession) -> list[tuple[str, bool, bool]] | None:
    """The flagged workspaces 0073 kept, or None when it kept nothing (the table is
    absent: dropped by a conversion, SQLite, or 0073 had run before #1590)."""
    connection = await db.connection()
    exists = await connection.run_sync(lambda sync: inspect(sync).has_table(HOLDING_TABLE))
    if not exists:
        return None
    rows = await db.execute(
        text(
            f"SELECT workspace_id, platform_drive_enabled, system_drive_enabled "
            f"FROM {HOLDING_TABLE} ORDER BY workspace_id"
        )
    )
    return [(str(w), bool(p), bool(s)) for w, p, s in rows.all()]


def _convert(
    iam: Any,
    rows: Sequence[tuple[str, bool, bool]],
    policies: Mapping[str, str],
    *,
    apply: bool,
) -> list[DriveFlagChange]:
    changes: list[DriveFlagChange] = []
    with as_service_account("api"):
        registered = {
            workspace_of(c.name) for c in iam.list_containers() if is_workspace_container(c.name)
        }
        recorded = _workspace_containers(policies)
        for workspace, platform, system in rows:
            if platform:
                if workspace not in registered:
                    changes.append(
                        DriveFlagChange(
                            workspace, "platform", "none", "the workspace is gone from IAM"
                        )
                    )
                elif apply and workspace not in recorded:
                    changes.append(
                        DriveFlagChange(
                            workspace, "platform", "none", "the workspace has no access policy"
                        )
                    )
                else:
                    if apply:
                        give_platform_files(iam, policies[recorded[workspace]], WRITE)
                    changes.append(
                        DriveFlagChange(
                            workspace,
                            "platform",
                            "converted",
                            "Platform Files, read and write, given in the workspace's offer "
                            "(GivenPlatformFiles), as platform_drive_enabled gave every role",
                        )
                    )
            if system:
                changes.append(
                    DriveFlagChange(
                        workspace,
                        "system",
                        "reported",
                        "not converted: System Files is the platform admin's to give (#1529); "
                        "the workspace's admins no longer reach the whole object storage",
                    )
                )
    return changes


async def convert_legacy_drive_flags(
    iam: Any, db: AsyncSession, *, apply: bool = True
) -> list[DriveFlagChange]:
    """Turn the drive flags 0073 kept into the workspaces' offers.

    For each workspace of ``workspace_drive_flags_legacy``: ``platform_drive_enabled``
    gives its people Platform Files read and write (``"converted"``),
    ``system_drive_enabled`` is reported and not converted (``"reported"``); a
    workspace IAM no longer registers is ``"none"``. Then the holding table is dropped
    (and ``db`` committed). An empty list: nothing was kept (the table is absent).
    Idempotent: a second run finds no table. ``apply=False``: the report alone,
    nothing changed, the table kept. The IAM writes are made as ``api`` in a worker
    thread, once the access policies are recorded (``container_defaults``)."""
    rows = await _holding_rows(db)
    if rows is None:
        logger.info("Drive flags: none kept by 0073 (nothing to convert)")
        return []
    policies = await offer_moves.access_policies(db) if apply else {}
    changes = await run_in_threadpool(lambda: _convert(iam, rows, policies, apply=apply))
    if apply:
        await db.execute(text(f"DROP TABLE IF EXISTS {HOLDING_TABLE}"))
        await db.commit()
    for change in changes:
        logger.info(f"Drive flags: {change}")
    return changes


__all__ = [
    "GROUP_PREFIX",
    "HOLDING_TABLE",
    "MIGRATION_NAME",
    "READ_POLICY",
    "WRITE_POLICY",
    "DriveFlagChange",
    "Report",
    "apply",
    "convert_legacy_drive_flags",
    "give_platform_files",
    "migrate",
    "workspace_of_group",
]
