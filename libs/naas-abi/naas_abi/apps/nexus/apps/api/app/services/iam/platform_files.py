"""Platform Files given with the workspace (#1590; ADR
``docs/adr/20261120_access_levels_and_groups.md``, "Platform Files").

Platform Files (``naas_abi/platform-drive``) is one tree shared by the whole platform,
decided at the platform (``platform_file``, ``policy_only``, #1529). A workspace gives it
to its people: Workspace settings › General › Platform Files is Off, Read, or Read and
write.

**Two platform policies, written once** and kept as this module writes them:

* "Platform Files · read": ``nexus:ListPlatformFiles``, ``GetPlatformFile`` on
  ``abi:nexus:platform_file/*``, and ``object_storage`` list and get on
  ``abi:object_storage:object/naas_abi/platform-drive`` and ``.../platform-drive/*``;
* "Platform Files · write": read, plus ``PutPlatformFile``, ``DeletePlatformFile`` and
  ``object_storage:PutObject``, ``PutObjectStream``, ``DeleteObject`` on the same keys.

**A platform group per workspace that has it**, "Platform Files · <W> (<workspace id>)",
holds one of them, unscoped. Its members are the people of W: Nexus keeps them in step
with W's membership groups ("<W> workspace", "<W> admins"):

* at each membership change made through ``MEMBERSHIPS`` (``follow``, where
  "Workspace admins" is kept in step) and through the IAM admin pages;
* when the setting changes (``set_workspace_platform_files``);
* at each start (``sync_platform_files``), which also deletes the group of a workspace
  that is gone.

Why not hold it on "<W> workspace": what a membership group holds at its own container
is that container's bound and grants nothing (core "Bounds", #1585), and IAM refuses an
unscoped attachment to a group a workspace owns. Why a group per workspace and not one
per mode: the setting is then IAM's alone (which policy the group holds, which only the
platform's grants may change), shared by every process, and a membership change is
decided for W alone (in W or not), whatever the person's other workspaces say.

**Who may change it:** the group and its attachment are platform names, which only
unscoped grants reach, and attaching a policy is held-checked ("grant only what you
hold"): the platform admin. Workspace and org admins read it.

**The legacy flags.** ``0073_drop_drive_flags.sql`` copies the flagged workspaces into
``workspace_drive_flags_legacy`` (PostgreSQL) before it drops the columns;
``convert_legacy_drive_flags`` (called by the ``access_model_v1`` migration, #1587)
turns ``platform_drive_enabled`` into Read and write, reports ``system_drive_enabled``
without converting it (System Files is the platform admin's alone, #1529), then drops
the holding table.

Everything is decided at the platform, whatever workspace a request names: someone who
has Platform Files through W also sees it while working in another workspace.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    PLATFORM,
    is_workspace_container,
    nexus_resource,
    workspace_of,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
    PrincipalRecord,
    new_id,
)
from naas_abi_core.services.iam.IAMService import group_resource
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.iam.policy import POLICY_VERSION, PolicyDocument
from naas_abi_core.services.object_storage.iam_catalog import object_parts
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

Mode = Literal["off", "read", "write"]
OFF: Mode = "off"
READ: Mode = "read"
WRITE: Mode = "write"
MODES: tuple[Mode, ...] = (OFF, READ, WRITE)

READ_POLICY = "Platform Files · read"
WRITE_POLICY = "Platform Files · write"
GROUP_PREFIX = "Platform Files · "

PLATFORM_DRIVE = "naas_abi/platform-drive"
HOLDING_TABLE = "workspace_drive_flags_legacy"

READ_ACTIONS: tuple[str, ...] = ("nexus:ListPlatformFiles", "nexus:GetPlatformFile")
WRITE_ACTIONS: tuple[str, ...] = ("nexus:PutPlatformFile", "nexus:DeletePlatformFile")
OBJECT_READ_ACTIONS: tuple[str, ...] = (
    "object_storage:ListObjects",
    "object_storage:ListObjectsRecursive",
    "object_storage:GetObject",
    "object_storage:GetObjectMetadata",
    "object_storage:GetObjectStream",
)
OBJECT_WRITE_ACTIONS: tuple[str, ...] = (
    "object_storage:PutObject",
    "object_storage:PutObjectStream",
    "object_storage:DeleteObject",
)

_KEPT = " Nexus keeps it (#1590): an edit is replaced at the next start."
DESCRIPTIONS: dict[str, str] = {
    READ_POLICY: (
        "Lists and reads Platform Files (naas_abi/platform-drive), in Nexus and in the "
        "object storage. Held by the Platform Files group of each workspace set to Read." + _KEPT
    ),
    WRITE_POLICY: (
        "Lists, reads, writes and deletes Platform Files (naas_abi/platform-drive), in "
        "Nexus and in the object storage. Held by the Platform Files group of each "
        "workspace set to Read and write." + _KEPT
    ),
}

_GROUP_NAME = re.compile(r"^Platform Files · (?:(?P<label>.*) )?\((?P<workspace>[^()]+)\)$")


@dataclass(frozen=True)
class DriveFlagChange:
    """One line of the conversion report of the legacy drive flags.

    ``flag``: ``"platform"`` (``platform_drive_enabled``) or ``"system"``
    (``system_drive_enabled``). ``action``: ``"converted"`` (the workspace now gives
    Platform Files, read and write), ``"reported"`` (kept out on purpose: System Files is
    the platform admin's alone) or ``"none"`` (nothing to do, ``detail`` says why)."""

    workspace_id: str
    flag: Literal["platform", "system"]
    action: Literal["converted", "reported", "none"]
    detail: str


@dataclass(frozen=True)
class PlatformFilesPolicies:
    read: str
    write: str

    def of(self, mode: Mode) -> str | None:
        return {READ: self.read, WRITE: self.write}.get(mode)


# -- the policies ------------------------------------------------------------------------


def platform_file_resources() -> list[str]:
    """Every Platform File, ``abi:nexus:platform_file/*``."""
    root = nexus_resource("platform_file", id=("platform",))
    return [root.rsplit("/", 1)[0] + "/*"]


def platform_drive_objects() -> list[str]:
    """The platform drive's folder and every object below it, in the object storage."""
    folder = resource_name("object_storage", "object", object_parts(PLATFORM_DRIVE), kind="path")
    return [folder, folder + "/*"]


def policy_document(mode: Mode) -> PolicyDocument:
    """The document of "Platform Files · read" (``READ``) or "· write" (``WRITE``):
    both halves, the Nexus actions and the object storage's (#1529)."""
    if mode not in (READ, WRITE):
        raise ValueError(f"No policy for {mode!r}")
    nexus = list(READ_ACTIONS) + (list(WRITE_ACTIONS) if mode == WRITE else [])
    objects = list(OBJECT_READ_ACTIONS) + (list(OBJECT_WRITE_ACTIONS) if mode == WRITE else [])
    statements = [
        {
            "sid": "PlatformFiles",
            "effect": "Allow",
            "actions": nexus,
            "resources": platform_file_resources(),
        },
        {
            "sid": "PlatformDrive",
            "effect": "Allow",
            "actions": objects,
            "resources": platform_drive_objects(),
        },
    ]
    return PolicyDocument.from_dict({"version": POLICY_VERSION, "statements": statements})


def _pages(listing: Any, **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _policy(iam: Any, name: str, mode: Mode) -> str:
    wanted = policy_document(mode)
    description = DESCRIPTIONS[name]
    for policy in _pages(iam.list_policies):
        if (policy.owner_scope, policy.name, policy.description) == (PLATFORM, name, description):
            if policy.document.to_dict() != wanted.to_dict():
                iam.update_policy(policy.id, expected_revision=policy.revision, document=wanted)
            return str(policy.id)
    return str(iam.create_policy(name, wanted, description=description).id)


def ensure_policies(iam: Any) -> PlatformFilesPolicies:
    """Find or make the two platform policies, their documents kept as written here.
    Idempotent. As ``api`` for no user."""
    with as_service_account("api"):
        return PlatformFilesPolicies(
            read=_policy(iam, READ_POLICY, READ),
            write=_policy(iam, WRITE_POLICY, WRITE),
        )


# -- the groups --------------------------------------------------------------------------


def group_name(workspace_id: str, label: str | None = None) -> str:
    """ "Platform Files · <W> (<workspace id>)": the id is how Nexus finds it again."""
    return f"{GROUP_PREFIX}{label} ({workspace_id})" if label else f"{GROUP_PREFIX}({workspace_id})"


def workspace_of_group(group: PrincipalRecord) -> str | None:
    """The workspace a platform group gives Platform Files for, or None."""
    if group.kind != "group" or group.owner_scope != PLATFORM or group.status == "deleted":
        return None
    if getattr(group, "level_group", False) or getattr(group, "membership_of", None):
        return None
    found = _GROUP_NAME.match(group.name or "")
    return found.group("workspace") if found else None


def platform_files_groups(iam: Any) -> dict[str, str]:
    """``{workspace id: group id}`` of every workspace that gives Platform Files (the
    first group by id, should there be two). As ``api``."""
    found: dict[str, str] = {}
    with as_service_account("api"):
        groups = _pages(iam.list_groups)
    for group in sorted(groups, key=lambda g: str(g.id)):
        workspace = workspace_of_group(group)
        if workspace is not None:
            found.setdefault(workspace, str(group.id))
    return found


def _mode_of_group(iam: Any, group_id: str, policies: PlatformFilesPolicies) -> Mode:
    with as_service_account("api"):
        held = {a.policy_id for a in iam.list_attachments(principal_id=group_id) if a.scope is None}
    if policies.write in held:
        return WRITE
    if policies.read in held:
        return READ
    return OFF


def _containers(iam: Any) -> dict[str, str]:
    """``{workspace id: container}`` of every workspace IAM registers."""
    found: dict[str, str] = {}
    for container in iam.list_containers():
        if is_workspace_container(container.name):
            workspace = workspace_of(container.name)
            if workspace:
                found[workspace] = container.name
    return found


def _container_of(iam: Any, workspace_id: str) -> str | None:
    return _containers(iam).get(workspace_id)


def people_of(iam: Any, container: str) -> set[str]:
    """The people of a workspace: the members of its membership groups ("<W>
    workspace", "<W> admins"). As ``api``. A workspace recorded before #1585 (roles
    attached to people, not groups) has none until #1587 converts it."""
    with as_service_account("api"):
        return set(iam.list_container_members(container))


def _label(iam: Any, container: str) -> str | None:
    """The workspace's label, read off its membership group ("<W> workspace")."""
    with as_service_account("api"):
        groups = _pages(iam.list_groups, scope=container)
    for group in groups:
        name = group.name or ""
        if getattr(group, "membership_of", None) == container and name.endswith(" workspace"):
            return name[: -len(" workspace")] or None
    return None


def _step(iam: Any, group_id: str, wanted: Iterable[str]) -> tuple[int, int]:
    """Make the group's members ``wanted``. As ``api``. ``(added, removed)``."""
    want = set(wanted)
    added = removed = 0
    with as_service_account("api"):
        have = set(iam.list_group_members(group_id))
        for principal_id in sorted(want - have):
            try:
                iam.add_group_member(group_id, principal_id)
                added += 1
            except (ValueError, IAMNotFoundError) as exc:
                logger.warning(f"{principal_id} could not join {group_id}: {exc}")
        for principal_id in sorted(have - want):
            if iam.remove_group_member(group_id, principal_id):
                removed += 1
    return added, removed


# -- reads -------------------------------------------------------------------------------


def workspace_platform_files(iam: Any, workspace_id: str) -> Mode:
    """The workspace's setting: what its Platform Files group holds (``OFF`` without
    one)."""
    group = platform_files_groups(iam).get(workspace_id)
    if group is None:
        return OFF
    return _mode_of_group(iam, group, ensure_policies(iam))


def may_set(iam: Any) -> bool:
    """Whether the caller (the ambient call context) may change the setting: make a
    group at the platform, which only unscoped grants reach (the platform admin)."""
    return bool(iam.authorize("iam:CreateGroup", group_resource(new_id("grp"))).allowed)


# -- changes -----------------------------------------------------------------------------


def set_workspace_platform_files(iam: Any, workspace_id: str, mode: str) -> Mode:
    """Give the people of ``workspace_id`` Platform Files: ``"off"``, ``"read"`` or
    ``"write"`` (read and write). Returns the mode after.

    The group and its policy are changed in the ambient call context (the caller's, for
    a route: IAM decides, and attaching is held-checked); its members are then made W's
    people as ``api`` (the change was authorized). ``PermissionDeniedError`` when the
    caller may not, ``IAMNotFoundError`` for a workspace IAM does not register,
    ``ValueError`` for another mode. Idempotent."""
    if mode not in MODES:
        raise ValueError(f"Platform Files is one of {', '.join(MODES)}, not {mode!r}")
    with as_service_account("api"):
        container = _container_of(iam, workspace_id)
    if container is None:
        raise IAMNotFoundError(f"Workspace {workspace_id} not found")
    policies = ensure_policies(iam)
    group = platform_files_groups(iam).get(workspace_id)
    if not may_set(iam):
        raise PermissionDeniedError(
            "iam:CreateGroup",
            group_resource(group or "*"),
            message="Only a platform admin gives Platform Files to a workspace",
        )
    if mode == OFF:
        if group is not None:
            iam.delete_group(group)
        return OFF
    made = False
    if group is None:
        from naas_abi.apps.nexus.apps.api.app.services.iam.group_descriptions import described

        name = group_name(workspace_id, _label(iam, container))
        group = str(iam.create_group(name, description=described(name, owner=PLATFORM)).id)
        made = True
    wanted = policies.write if mode == WRITE else policies.read
    other = policies.read if mode == WRITE else policies.write
    with as_service_account("api"):
        held = {a.policy_id for a in iam.list_attachments(principal_id=group) if a.scope is None}
    try:
        if wanted not in held:
            iam.attach_policy(wanted, group)
        if other in held:
            iam.detach_policy(other, group)
    except Exception:
        if made:
            with as_service_account("api"):
                iam.delete_group(group)
        raise
    _step(iam, group, people_of(iam, container))
    return mode  # type: ignore[return-value]


def follow(iam: Any, principal_id: str) -> None:
    """Keep one person's Platform Files in step with their workspaces: in the group of
    each workspace they belong to (a membership group of it), in no other. As ``api``.
    Called after each membership change (``MEMBERSHIPS``, the IAM admin pages)."""
    groups = platform_files_groups(iam)
    if not groups:
        return
    with as_service_account("api"):
        mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
        workspaces = {
            workspace_of(m.container)
            for m in iam.list_memberships(principal_id)
            if is_workspace_container(m.container)
        }
        for workspace, group in groups.items():
            if workspace in workspaces and group not in mine:
                try:
                    iam.add_group_member(group, principal_id)
                except (ValueError, IAMNotFoundError) as exc:
                    logger.warning(f"{principal_id} could not join {group}: {exc}")
            elif workspace not in workspaces and group in mine:
                iam.remove_group_member(group, principal_id)


def forget_workspace(iam: Any, workspace_id: str) -> bool:
    """Delete the Platform Files group of a deleted workspace, with what it gave. As
    ``api``. Whether there was one."""
    group = platform_files_groups(iam).get(workspace_id)
    if group is None:
        return False
    with as_service_account("api"):
        iam.delete_group(group)
    return True


def sync_platform_files(iam: Any) -> tuple[int, int]:
    """Every workspace's Platform Files group made its people (and that of a workspace
    gone, deleted). Run at each start and after a migration that moves memberships
    without ``MEMBERSHIPS`` (#1587). As ``api``. ``(added, removed)``."""
    groups = platform_files_groups(iam)
    if not groups:
        return 0, 0
    with as_service_account("api"):
        containers = _containers(iam)
    added = removed = 0
    for workspace, group in groups.items():
        container = containers.get(workspace)
        if container is None:
            forget_workspace(iam, workspace)
            continue
        step = _step(iam, group, people_of(iam, container))
        added, removed = added + step[0], removed + step[1]
    return added, removed


def ensure_configured(iam: Any) -> None:
    """At start: the two policies, then every group in step. As ``api``."""
    ensure_policies(iam)
    added, removed = sync_platform_files(iam)
    if added or removed:
        logger.info(f"Platform Files kept in step with the workspaces: +{added} -{removed}")


# -- the legacy drive flags (#1529 dropped them, #1587 converts them) ---------------------


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
    iam: Any, rows: Sequence[tuple[str, bool, bool]], *, apply: bool
) -> list[DriveFlagChange]:
    changes: list[DriveFlagChange] = []
    with as_service_account("api"):
        containers = _containers(iam)
        for workspace, platform, system in rows:
            if platform:
                container = containers.get(workspace)
                if container is None:
                    changes.append(
                        DriveFlagChange(
                            workspace, "platform", "none", "the workspace is gone from IAM"
                        )
                    )
                else:
                    if apply:
                        set_workspace_platform_files(iam, workspace, WRITE)
                    people = len(people_of(iam, container))
                    changes.append(
                        DriveFlagChange(
                            workspace,
                            "platform",
                            "converted",
                            f"Platform Files · read and write for the people of the workspace "
                            f"({people} now), as platform_drive_enabled gave every role",
                        )
                    )
            if system:
                changes.append(
                    DriveFlagChange(
                        workspace,
                        "system",
                        "reported",
                        "not converted: System Files is the platform admin's alone (#1529); "
                        "the workspace's admins no longer reach the whole object storage",
                    )
                )
    return changes


async def convert_legacy_drive_flags(
    iam: Any, db: AsyncSession, *, apply: bool = True
) -> list[DriveFlagChange]:
    """Turn the drive flags 0073 kept into the workspaces' Platform Files setting.

    For each workspace of ``workspace_drive_flags_legacy``: ``platform_drive_enabled``
    gives its people Platform Files read and write (``"converted"``),
    ``system_drive_enabled`` is reported and not converted (``"reported"``); a
    workspace IAM no longer registers is ``"none"``. Then the holding table is dropped
    (and ``db`` committed). An empty list: nothing was kept (the table is absent).
    Idempotent: a second run finds no table. ``apply=False``: the report alone,
    nothing changed, the table kept. The IAM writes are made as ``api`` in a worker
    thread; run it after the memberships are in their groups, or call
    ``sync_platform_files`` once they are."""
    rows = await _holding_rows(db)
    if rows is None:
        logger.info("Drive flags: none kept by 0073 (nothing to convert)")
        return []
    changes = await run_in_threadpool(lambda: _convert(iam, rows, apply=apply))
    if apply:
        await db.execute(text(f"DROP TABLE IF EXISTS {HOLDING_TABLE}"))
        await db.commit()
    for change in changes:
        logger.info(f"Drive flags: {change}")
    return changes


__all__ = [
    "DESCRIPTIONS",
    "GROUP_PREFIX",
    "HOLDING_TABLE",
    "MODES",
    "OFF",
    "READ",
    "READ_POLICY",
    "WRITE",
    "WRITE_POLICY",
    "DriveFlagChange",
    "Mode",
    "PlatformFilesPolicies",
    "convert_legacy_drive_flags",
    "ensure_configured",
    "ensure_policies",
    "follow",
    "forget_workspace",
    "group_name",
    "may_set",
    "people_of",
    "platform_files_groups",
    "policy_document",
    "set_workspace_platform_files",
    "sync_platform_files",
    "workspace_platform_files",
]
