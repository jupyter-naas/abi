"""Each organization and each workspace has its own access policy and two default
groups (``AGENTS.md``, "Access policies and default groups").

- **"<O> access"**, owned by the platform: what organization O may use. A new
  organization's allows nothing (``nothing_document``): the platform admin widens
  it. It is attached to "<O> admins" below the organization, so O's owners and
  admins use what it allows in each of O's workspaces and derive policies from it.
- **"<W> access"**, owned by workspace W and a sub-policy of its organization's
  (with no parent for a workspace in no organization): what W makes available to
  its people. A new workspace's allows nothing; whoever holds more widens it, its
  owners and admins narrow it. It is attached to "<W> admins" at W. Policies made
  in W for its people are sub-policies of it, so narrowing it narrows each of them.
- **"<X> members"** (whoever holds a role at X) and **"<X> admins"** (its admins
  and owners), owned by X, kept in step with the roles held there (``sync``): a
  role given, changed or taken, an invitation claimed. A group every member joins
  carries nothing by default: the ceiling is the access policy, not a group.

IAM holds the policies and the groups; ``container_defaults`` (Nexus's table) says
which they are, by the container's IAM name. Everything here is written as ``api``
for no user: it follows a creation or a role change the route already authorized.

The upgrade (``migrate``, recorded in ``iam_migrations`` as ``container_defaults_v1``)
gives existing organizations and workspaces theirs once: the access policies the
sets' move made (``policy_tree``) are kept, a workspace's moved to the workspace
with what is below it that its organization owned (``iam.move_policies``), and
neither is attached to the admins group, which would give its people what the
move kept from them (features). Organizations and workspaces made after the sets'
move get new ones, which allow nothing. Nobody gains or loses access.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    org_below,
    org_container,
    workspace_container,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    Policy,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.names import PLATFORM
from naas_abi_core.services.iam.policy import POLICY_VERSION
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

MIGRATION_NAME = "container_defaults_v1"
ROLES = ("owner", "admin", "member", "viewer")
ADMIN_ROLES = frozenset({"owner", "admin"})
NOTHING_SID = "Nothing"

ORG_ACCESS = (
    "What organization {label} may use. The platform administrators widen it; its "
    'admins and owners hold it below the organization (through "{label} admins"). '
    "Its workspaces' access policies are sub-policies of it."
)
WORKSPACE_ACCESS = (
    "What workspace {label} makes available to its people, within its organization's. "
    'Its owners and admins narrow it (through "{label} admins" they hold it); policies '
    "made here for its people are sub-policies of it."
)
ORGLESS_WORKSPACE_ACCESS = (
    "What workspace {label} makes available to its people. It belongs to no "
    "organization, so the platform administrators widen it; its owners and admins narrow "
    "it. Policies made here for its people are sub-policies of it."
)

NOTES = (
    "The access policies the sets' move made are kept; neither an organization's nor a "
    "workspace's is attached to its admins group, which would give its admins and owners "
    "what the move kept from them (features). Attach it there to let them use it and "
    "derive from it.",
    "A workspace's access policy and what was below it that its organization owned now "
    "belong to the workspace: its owners and admins manage them (each change still checked "
    "against what they hold).",
)


def nothing_document() -> dict[str, Any]:
    """An Allow no name matches (a module id holds no NUL): what a new access policy
    lets through, and bounds below it. Not a Deny, which a widening would have to
    lift."""
    return {
        "version": POLICY_VERSION,
        "statements": [
            {
                "sid": NOTHING_SID,
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": ["${scope}/module:agent/%00"],
            }
        ],
    }


def access_name(label: str) -> str:
    return f"{label} access"


def members_name(label: str) -> str:
    return f"{label} members"


def admins_name(label: str) -> str:
    return f"{label} admins"


@dataclass(frozen=True)
class DefaultsRecord:
    container: str
    access_policy_id: str | None
    members_group_id: str | None
    admins_group_id: str | None


class DefaultsStore(Protocol):
    """Where the defaults of a container are recorded, in the caller's transaction."""

    async def get(self, container: str) -> DefaultsRecord | None: ...

    async def put(self, record: DefaultsRecord) -> None: ...

    async def delete_within(self, container: str) -> None:
        """Forget the container's record and those of the containers inside it."""
        ...


class SqlDefaultsStore:
    """``container_defaults`` through the session of the request or the start-up
    step: flushed with it, committed by its owner."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, container: str) -> DefaultsRecord | None:
        row = (
            await self.db.execute(
                text(
                    "SELECT container, access_policy_id, members_group_id, admins_group_id "
                    "FROM container_defaults WHERE container = :c"
                ),
                {"c": container},
            )
        ).first()
        return DefaultsRecord(*row) if row else None

    async def all(self) -> list[DefaultsRecord]:
        rows = await self.db.execute(
            text(
                "SELECT container, access_policy_id, members_group_id, admins_group_id "
                "FROM container_defaults"
            )
        )
        return [DefaultsRecord(*row) for row in rows.all()]

    async def put(self, record: DefaultsRecord) -> None:
        await self.db.execute(
            text("DELETE FROM container_defaults WHERE container = :c"), {"c": record.container}
        )
        await self.db.execute(
            text(
                "INSERT INTO container_defaults "
                "(container, access_policy_id, members_group_id, admins_group_id, created_at) "
                "VALUES (:c, :p, :m, :a, CURRENT_TIMESTAMP)"
            ),
            {
                "c": record.container,
                "p": record.access_policy_id,
                "m": record.members_group_id,
                "a": record.admins_group_id,
            },
        )
        await self.db.flush()

    async def delete_within(self, container: str) -> None:
        await self.db.execute(
            text("DELETE FROM container_defaults WHERE container = :c OR container LIKE :below"),
            {"c": container, "below": container.replace("%", r"\%") + "/%"},
        )
        await self.db.flush()


def defaults_store_of(adapter: Any) -> DefaultsStore | None:
    """The store an adapter of organizations or workspaces records defaults in
    (``container_defaults()``, in its own transaction); None for one that keeps no
    database (a test's), which then makes none."""
    factory = getattr(adapter, "container_defaults", None)
    return factory() if callable(factory) else None


# -- in IAM ---------------------------------------------------------------------------


def _as_api(work: Callable[[Any], Any]) -> Any:
    iam = runtime.iam()
    with as_service_account("api"):
        return work(iam)


def make_org(iam: Any, org_id: str, label: str) -> DefaultsRecord:
    """ "<O> access" (platform, nothing) attached to "<O> admins" below the org, and
    the two groups. As ``api``."""
    container = org_container(org_id)
    access = iam.create_policy(
        access_name(label),
        nothing_document(),
        description=ORG_ACCESS.format(label=label),
    )
    members, admins = _make_groups(iam, container, label)
    iam.attach_policy(access.id, admins, org_below(org_id))
    return DefaultsRecord(container, access.id, members, admins)


def make_workspace(
    iam: Any,
    org_id: str | None,
    workspace_id: str,
    label: str,
    *,
    parent: str | None,
) -> DefaultsRecord:
    """ "<W> access" (W's, nothing, a sub-policy of ``parent``: the org's access)
    attached to "<W> admins" at W, and the two groups. As ``api``."""
    container = workspace_container(org_id, workspace_id)
    access = iam.create_policy(
        access_name(label),
        nothing_document(),
        description=(WORKSPACE_ACCESS if org_id else ORGLESS_WORKSPACE_ACCESS).format(label=label),
        scope=container,
        parent=parent,
    )
    members, admins = _make_groups(iam, container, label)
    iam.attach_policy(access.id, admins, container)
    return DefaultsRecord(container, access.id, members, admins)


def _make_groups(iam: Any, container: str, label: str) -> tuple[str, str]:
    members = iam.create_group(members_name(label), scope=container)
    admins = iam.create_group(admins_name(label), scope=container)
    return str(members.id), str(admins.id)


def role_holders(iam: Any, container: str) -> dict[str, set[str]]:
    """``{principal: roles}`` of the users holding a built-in role at ``container``
    itself (an org-wide mirror below an organization is not "there")."""
    held: dict[str, set[str]] = {}
    for role in ROLES:
        for attachment in iam.list_attachments(policy_id=f"builtin.{role}"):
            if attachment.scope == container:
                held.setdefault(attachment.principal_id, set()).add(role)
    users: dict[str, set[str]] = {}
    for principal_id, roles_held in held.items():
        try:
            if iam.get_principal(principal_id).kind == "user":
                users[principal_id] = roles_held
        except (IAMNotFoundError, ResourceNotFoundError):
            continue
    return users


def sync(iam: Any, record: DefaultsRecord) -> tuple[int, int]:
    """Make the groups' members the role holders: every one of them in "<X>
    members", the admins and owners in "<X> admins". As ``api``. Returns
    ``(added, removed)``."""
    holders = role_holders(iam, record.container)
    wanted = {
        record.members_group_id: set(holders),
        record.admins_group_id: {p for p, held in holders.items() if held & ADMIN_ROLES},
    }
    added = removed = 0
    for group_id, members in wanted.items():
        if not group_id:
            continue
        try:
            have = set(iam.list_group_members(group_id))
        except (IAMNotFoundError, ResourceNotFoundError):
            logger.warning(f"Group {group_id} of {record.container} is gone: not kept in step")
            continue
        for principal_id in sorted(members - have):
            try:
                iam.add_group_member(group_id, principal_id)
                added += 1
            except (ValueError, IAMConflictError, IAMNotFoundError) as exc:
                logger.warning(f"{principal_id} could not join {group_id}: {exc}")
        for principal_id in sorted(have - members):
            iam.remove_group_member(group_id, principal_id)
            removed += 1
    return added, removed


# -- the service ----------------------------------------------------------------------


@dataclass
class ContainerDefaults:
    """Makes, keeps in step and forgets the defaults of organizations and workspaces.
    Remembers each record it saw (``_known``); one it never saw is read from the
    database (``session_factory``, set at start) when its roles change."""

    session_factory: Callable[[], Any] | None = None
    _known: dict[str, DefaultsRecord] = field(default_factory=dict)

    def forget_all(self) -> None:
        self._known.clear()

    async def org_created(
        self, store: DefaultsStore | None, org_id: str, label: str
    ) -> DefaultsRecord | None:
        if store is None:
            return None
        record = await run_in_threadpool(lambda: _as_api(lambda iam: make_org(iam, org_id, label)))
        await store.put(record)
        self._known[record.container] = record
        await self.sync_scope(record.container)
        return record

    async def workspace_created(
        self,
        store: DefaultsStore | None,
        org_id: str | None,
        workspace_id: str,
        label: str,
    ) -> DefaultsRecord | None:
        if store is None:
            return None
        parent = None
        if org_id:
            org_record = await store.get(org_container(org_id))
            if org_record is None:
                logger.warning(
                    f"Organization {org_id} has no access policy: workspace {workspace_id}'s "
                    "has no parent until the next start makes it"
                )
            else:
                parent = org_record.access_policy_id
        record = await run_in_threadpool(
            lambda: _as_api(
                lambda iam: make_workspace(iam, org_id, workspace_id, label, parent=parent)
            )
        )
        await store.put(record)
        self._known[record.container] = record
        await self.sync_scope(record.container)
        return record

    async def dropped(self, store: DefaultsStore | None, container: str) -> None:
        """After IAM deleted the container (with what it owned): forget its records
        and, for an organization, delete its access policy, the platform's."""
        record = self._known.get(container)
        if record is None and store is not None:
            record = await store.get(container)
        for known in [c for c in self._known if c == container or c.startswith(container + "/")]:
            del self._known[known]
        if store is not None:
            await store.delete_within(container)
        if record is None or not record.access_policy_id or not is_org_container(container):
            return
        policy_id = record.access_policy_id

        def delete(iam: Any) -> None:
            try:
                iam.delete_policy(policy_id)
            except (IAMNotFoundError, ResourceNotFoundError):
                pass
            except IAMConflictError as exc:
                logger.warning(f"The access policy {policy_id} of {container} stays: {exc}")

        await run_in_threadpool(lambda: _as_api(delete))

    async def record_of(self, container: str) -> DefaultsRecord | None:
        found = self._known.get(container)
        if found is not None or self.session_factory is None:
            return found
        async with self.session_factory() as db:
            found = await SqlDefaultsStore(db).get(container)
        if found is not None:
            self._known[container] = found
        return found

    async def sync_scope(self, scope: str) -> None:
        """Keep the default groups of ``scope`` (an organization's or a workspace's
        container) in step with the roles held there. Never fails the change that
        asked: a failure is logged."""
        if not (is_org_container(scope) or is_workspace_container(scope)):
            return
        try:
            record = await self.record_of(scope)
            if record is None:
                return
            await run_in_threadpool(lambda: _as_api(lambda iam: sync(iam, record)))
        except Exception:  # noqa: BLE001 - the role change stands; the groups follow at the next one
            logger.exception(f"The default groups of {scope} are not in step with its roles")


CONTAINER_DEFAULTS = ContainerDefaults()


# -- the upgrade ----------------------------------------------------------------------


@dataclass
class Report:
    made: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)
    moved: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def _org_access_made_by_move(policy: Policy, org_id: str) -> bool:
    from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree import made_by_move

    return (
        made_by_move(policy)
        and policy.owner_scope == PLATFORM
        and str(policy.description).startswith(f"What organization {org_id} uses:")
    )


def _workspace_access_made_by_move(policy: Policy, workspace_id: str) -> bool:
    from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree import made_by_move

    return made_by_move(policy) and str(policy.description).startswith(
        f"What workspace {workspace_id} uses, within its organization's:"
    )


def _all_policies(iam: Any) -> list[Policy]:
    found: list[Policy] = []
    after: str | None = None
    while True:
        page = iam.list_policies(limit=500, after=after)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _below_owned_by(iam: Any, policy: Policy) -> list[str]:
    """The policies below ``policy`` owned where it is, nearest first."""
    found: list[str] = []
    level = [policy.id]
    for _depth in range(8):
        following = []
        for parent_id in level:
            for sub in iam.list_sub_policies(parent_id):
                if sub.owner_scope == policy.owner_scope and sub.id not in found:
                    found.append(sub.id)
                    following.append(sub.id)
        level = following
    return found


def adopt_workspace_access(iam: Any, policy: Policy, container: str, report: Report) -> str:
    """Move the sets' move's "<W> access" to W, with what is below it that W's
    organization (or, in none, the platform) owned. As ``api``."""
    if policy.owner_scope == container:
        return policy.id
    owners = {policy.id: container, **dict.fromkeys(_below_owned_by(iam, policy), container)}
    try:
        iam.move_policies(owners)
    except (ValueError, IAMConflictError) as exc:
        report.notes.append(
            f"{policy.id} ({policy.name}) stays {policy.owner_scope}'s, not {container}'s: {exc}"
        )
        return policy.id
    report.moved[container] = sorted(owners)
    return policy.id


def plan_and_apply(
    iam: Any,
    orgs: Mapping[str, str],
    workspaces: Mapping[str, tuple[str | None, str]],
    known: Mapping[str, DefaultsRecord],
) -> tuple[list[DefaultsRecord], Report]:
    """For each organization (``{id: name}``) and workspace (``{id: (org, name)}``)
    with no record yet, adopt what the sets' move made or make new defaults, then
    put the groups in step with the roles. As ``api``; pure of the database."""
    report = Report(notes=list(NOTES))
    policies = _all_policies(iam)
    records: dict[str, DefaultsRecord] = dict(known)
    made: list[DefaultsRecord] = []
    for org_id, label in sorted(orgs.items()):
        container = org_container(org_id)
        if container in records:
            continue
        try:
            found = next((p for p in policies if _org_access_made_by_move(p, org_id)), None)
            if found is not None:
                members, admins = _make_groups(iam, container, label)
                record = DefaultsRecord(container, found.id, members, admins)
                report.adopted.append(container)
            else:
                record = make_org(iam, org_id, label)
                report.made.append(container)
            records[container] = record
            made.append(record)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"No access policy and groups for {container}")
            report.failed.append(f"{container}: {exc}")
    for workspace_id, (org_id, label) in sorted(workspaces.items()):
        container = workspace_container(org_id, workspace_id)
        if container in records:
            continue
        try:
            found = next(
                (p for p in policies if _workspace_access_made_by_move(p, workspace_id)), None
            )
            if found is not None:
                access = adopt_workspace_access(iam, found, container, report)
                members, admins = _make_groups(iam, container, label)
                record = DefaultsRecord(container, access, members, admins)
                report.adopted.append(container)
            else:
                org_record = records.get(org_container(org_id)) if org_id else None
                if org_id and org_record is None:
                    raise RuntimeError(f"its organization {org_id} has no access policy")
                record = make_workspace(
                    iam,
                    org_id,
                    workspace_id,
                    label,
                    parent=org_record.access_policy_id if org_record else None,
                )
                report.made.append(container)
            records[container] = record
            made.append(record)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"No access policy and groups for {container}")
            report.failed.append(f"{container}: {exc}")
    for record in made:
        try:
            sync(iam, record)
        except Exception as exc:  # noqa: BLE001 - the groups follow at the next role change
            logger.exception(f"The groups of {record.container} are not in step")
            report.failed.append(f"{record.container}: {exc}")
    return made, report


async def read_nexus(
    db: AsyncSession,
) -> tuple[dict[str, str], dict[str, tuple[str | None, str]]]:
    """Nexus's organizations (``{id: name}``) and workspaces (``{id: (org, name)}``)."""
    orgs = {
        str(row[0]): str(row[1] or row[0])
        for row in (await db.execute(text("SELECT id, name FROM organizations"))).all()
    }
    workspaces = {
        str(row[0]): (
            (str(row[1]) if row[1] and str(row[1]) in orgs else None),
            str(row[2] or row[0]),
        )
        for row in (
            await db.execute(text("SELECT id, organization_id, name FROM workspaces"))
        ).all()
    }
    return orgs, workspaces


async def migrate(db: AsyncSession, defaults: ContainerDefaults = CONTAINER_DEFAULTS) -> Report:
    """Give every organization and workspace with none its access policy and default
    groups (adopting what the sets' move made), then record ``container_defaults_v1``
    once nothing failed. Runs at every start: only what has no record is touched."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_names import recorded

    store = SqlDefaultsStore(db)
    orgs, workspaces = await read_nexus(db)
    known = {record.container: record for record in await store.all()}
    made, report = await run_in_threadpool(
        lambda: _as_api(lambda iam: plan_and_apply(iam, orgs, workspaces, known))
    )
    for record in made:
        await store.put(record)
    if not report.failed and not await recorded(db, MIGRATION_NAME):
        await db.execute(
            text(
                "INSERT INTO iam_migrations (name, applied_at, report) "
                "VALUES (:n, CURRENT_TIMESTAMP, :r)"
            ),
            {"n": MIGRATION_NAME, "r": report.to_json()},
        )
    await db.commit()
    for record in [*known.values(), *made]:
        defaults._known[record.container] = record
    if made:
        logger.info(
            f"Access policies and default groups: {len(report.made)} made, "
            f"{len(report.adopted)} kept from the sets' move"
            + (f"; notes: {' '.join(report.notes)}" if report.adopted else "")
        )
    for failure in report.failed:
        logger.error(f"Access policy and default groups not made: {failure}")
    return report


__all__ = [
    "ADMIN_ROLES",
    "CONTAINER_DEFAULTS",
    "ContainerDefaults",
    "DefaultsRecord",
    "DefaultsStore",
    "MIGRATION_NAME",
    "SqlDefaultsStore",
    "access_name",
    "admins_name",
    "defaults_store_of",
    "make_org",
    "make_workspace",
    "members_name",
    "migrate",
    "nothing_document",
    "sync",
]
