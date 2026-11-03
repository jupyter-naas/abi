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
import re
import time
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
        # A prefix compared as text, never a LIKE pattern: ids may hold ``_`` or ``%``.
        prefix = container + "/"
        await self.db.execute(
            text(
                "DELETE FROM container_defaults "
                "WHERE container = :c OR substr(container, 1, :n) = :prefix"
            ),
            {"c": container, "n": len(prefix), "prefix": prefix},
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


def moves_pending() -> bool:
    """While the sets' or the names' move is not recorded, nothing is made: the move
    makes the access policies, and ``migrate`` adopts them at the start that follows."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import container_names, policy_tree

    return policy_tree.pending() or container_names.pending()


def _pages(listing: Callable[..., Any], **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _own_groups(iam: Any, container: str) -> dict[str, str]:
    """``{name: id}`` of the live groups ``container`` owns."""
    return {
        str(g.name): str(g.id)
        for g in _pages(iam.list_groups, scope=container)
        if g.owner_scope == container and g.status != "deleted"
    }


def _access_made_before(
    iam: Any, owner: str, name: str, description: str, *, scope: str | None
) -> str | None:
    """An access policy an earlier attempt made and never recorded (it stopped
    before its record was written): found by owner, name and description."""
    for policy in _pages(iam.list_policies, scope=scope):
        if (policy.owner_scope, policy.name, policy.description) == (owner, name, description):
            return str(policy.id)
    return None


def _undo(iam: Any, made: list[tuple[str, Any]]) -> None:
    """Take back, last first, what one attempt made, so a failure leaves nothing
    behind that no record names."""
    for kind, what in reversed(made):
        try:
            if kind == "attachment":
                iam.detach_policy(*what)
            elif kind == "group":
                iam.delete_group(what)
            else:
                iam.delete_policy(what)
        except Exception:  # noqa: BLE001 - the original failure is what is raised
            logger.exception(f"Could not take back the {kind} {what}")


def _ensure(
    iam: Any,
    *,
    container: str,
    label: str,
    access: str | None,
    make_access: Callable[[], str],
    find_access: Callable[[], str | None],
    attach_at: str | None,
) -> DefaultsRecord:
    """The access policy (``access``, else one made before and unrecorded, else a new
    one), the two groups (found by name, else made) and, with ``attach_at``, the
    access policy attached to the admins group there. On a failure, what this call
    made is taken back."""
    made: list[tuple[str, Any]] = []
    try:
        if access is None:
            access = find_access()
        if access is None:
            access = make_access()
            made.append(("policy", access))
        groups = _own_groups(iam, container)
        ids: list[str] = []
        for name in (members_name(label), admins_name(label)):
            if name not in groups:
                groups[name] = str(iam.create_group(name, scope=container).id)
                made.append(("group", groups[name]))
            ids.append(groups[name])
        members, admins = ids
        if attach_at is not None and not any(
            (a.policy_id, a.scope) == (access, attach_at)
            for a in iam.list_attachments(principal_id=admins)
        ):
            iam.attach_policy(access, admins, attach_at)
            made.append(("attachment", (access, admins, attach_at)))
    except Exception:
        _undo(iam, made)
        raise
    return DefaultsRecord(container, access, members, admins)


def make_org(iam: Any, org_id: str, label: str, *, adopt: str | None = None) -> DefaultsRecord:
    """ "<O> access" (the platform's, allowing nothing) attached to "<O> admins"
    below the organization, and the two groups; with ``adopt``, that policy instead,
    attached to nothing. Idempotent, and a failure leaves nothing. As ``api``."""
    name, description = access_name(label), ORG_ACCESS.format(label=label)
    return _ensure(
        iam,
        container=org_container(org_id),
        label=label,
        access=adopt,
        make_access=lambda: str(
            iam.create_policy(name, nothing_document(), description=description).id
        ),
        find_access=lambda: _access_made_before(iam, PLATFORM, name, description, scope=None),
        attach_at=None if adopt else org_below(org_id),
    )


def make_workspace(
    iam: Any,
    org_id: str | None,
    workspace_id: str,
    label: str,
    *,
    parent: str | None,
    adopt: str | None = None,
) -> DefaultsRecord:
    """ "<W> access" (the workspace's, allowing nothing, a sub-policy of ``parent``:
    the organization's access) attached to "<W> admins" at the workspace, and the two
    groups; with ``adopt``, that policy instead, attached to nothing. Idempotent, and a
    failure leaves nothing. As ``api``."""
    container = workspace_container(org_id, workspace_id)
    name = access_name(label)
    description = (WORKSPACE_ACCESS if org_id else ORGLESS_WORKSPACE_ACCESS).format(label=label)
    return _ensure(
        iam,
        container=container,
        label=label,
        access=adopt,
        make_access=lambda: str(
            iam.create_policy(
                name, nothing_document(), description=description, scope=container, parent=parent
            ).id
        ),
        find_access=lambda: _access_made_before(iam, container, name, description, scope=container),
        attach_at=None if adopt else container,
    )


def forget_made(iam: Any, record: DefaultsRecord) -> None:
    """Take back the IAM side of a record that could not be written (its groups, its
    access policy). As ``api``."""
    made: list[tuple[str, Any]] = []
    if record.access_policy_id:
        made.append(("policy", record.access_policy_id))
    for group in (record.members_group_id, record.admins_group_id):
        if group:
            made.append(("group", group))
    for attachment in (
        iam.list_attachments(principal_id=record.admins_group_id) if record.admins_group_id else []
    ):
        made.append(
            ("attachment", (attachment.policy_id, record.admins_group_id, attachment.scope))
        )
    _undo(iam, made)


Holders = dict[str, set[str]]


def is_user(principal_id: str) -> bool:
    """Roles are for users (``usr_`` ids): never a group or a service account."""
    return principal_id.startswith("usr_")


def holders_by_container(iam: Any) -> dict[str, Holders]:
    """``{container: {user principal: roles}}`` of every built-in role held at a
    container itself (an org-wide mirror below an organization is not "at" it), in one
    pass over the four roles' attachments."""
    found: dict[str, Holders] = {}
    for role in ROLES:
        for attachment in iam.list_attachments(policy_id=f"builtin.{role}"):
            if attachment.scope and is_user(attachment.principal_id):
                found.setdefault(attachment.scope, {}).setdefault(
                    attachment.principal_id, set()
                ).add(role)
    return found


def role_holders(iam: Any, container: str) -> Holders:
    return holders_by_container(iam).get(container, {})


def sync(iam: Any, record: DefaultsRecord, holders: Holders) -> tuple[int, int]:
    """Make the groups' members the role holders (``holders``: ``{principal: roles}``
    at the container): every one of them in "<X> members", the admins and owners in
    "<X> admins". As ``api``. Returns ``(added, removed)``."""
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

# How long a container with no record is taken to have none before the database is
# read again (one made in another process since is followed after that).
MISS_SECONDS = 60.0


@dataclass
class ContainerDefaults:
    """Makes, keeps in step and forgets the defaults of organizations and workspaces.
    Remembers each record it saw (``_known``), and for ``MISS_SECONDS`` a container it
    found none for (``_missing``); one it never saw is read from the database
    (``session_factory``, set at start) when its roles change."""

    session_factory: Callable[[], Any] | None = None
    _known: dict[str, DefaultsRecord] = field(default_factory=dict)
    _missing: dict[str, float] = field(default_factory=dict)

    def forget_all(self) -> None:
        self._known.clear()
        self._missing.clear()

    def remember(self, record: DefaultsRecord) -> None:
        self._known[record.container] = record
        self._missing.pop(record.container, None)

    async def _record(
        self, store: DefaultsStore, make: Callable[[Any], DefaultsRecord]
    ) -> DefaultsRecord:
        record = await run_in_threadpool(lambda: _as_api(make))
        try:
            await store.put(record)
        except Exception:
            await run_in_threadpool(lambda: _as_api(lambda iam: forget_made(iam, record)))
            raise
        self.remember(record)
        await self.sync_scope(record.container)
        return record

    async def org_created(
        self, store: DefaultsStore | None, org_id: str, label: str
    ) -> DefaultsRecord | None:
        """None with no store (a test's adapter), or while the moves are pending: the
        start after them gives the organization its own."""
        if store is None or moves_pending():
            return None
        return await self._record(store, lambda iam: make_org(iam, org_id, label))

    async def workspace_created(
        self,
        store: DefaultsStore | None,
        org_id: str | None,
        workspace_id: str,
        label: str,
    ) -> DefaultsRecord | None:
        if store is None or moves_pending():
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
        return await self._record(
            store, lambda iam: make_workspace(iam, org_id, workspace_id, label, parent=parent)
        )

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
        missed = self._missing.get(container)
        if missed is not None and time.monotonic() - missed < MISS_SECONDS:
            return None
        async with self.session_factory() as db:
            found = await SqlDefaultsStore(db).get(container)
        if found is None:
            self._missing[container] = time.monotonic()
        else:
            self.remember(found)
        return found

    async def sync_scope(self, scope: str) -> None:
        """Keep the default groups of ``scope`` (an organization's or a workspace's
        container) in step with the roles held there (``MEMBERSHIPS.members``). Never
        fails the change that asked: a failure is logged."""
        if not (is_org_container(scope) or is_workspace_container(scope)):
            return
        try:
            record = await self.record_of(scope)
            if record is None:
                return
            from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

            holders: Holders = {}
            for member in await MEMBERSHIPS.members(scope):
                if is_user(member.principal_id):
                    holders[member.principal_id] = {member.role}
            await run_in_threadpool(lambda: _as_api(lambda iam: sync(iam, record, holders)))
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


_ORG_MADE = re.compile(r"^What organization (\S+) uses:")
_WORKSPACE_MADE = re.compile(r"^What workspace (\S+) uses, within its organization's:")


def made_by_move(iam: Any) -> tuple[dict[str, Policy], dict[str, Policy]]:
    """The access policies the sets' move made, by organization and by workspace id
    (found by their description)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree import (
        made_by_move as by_move,
    )

    orgs: dict[str, Policy] = {}
    workspaces: dict[str, Policy] = {}
    for policy in _pages(iam.list_policies):
        if not by_move(policy):
            continue
        description = str(policy.description)
        if (found := _ORG_MADE.match(description)) and policy.owner_scope == PLATFORM:
            orgs.setdefault(found.group(1), policy)
        elif found := _WORKSPACE_MADE.match(description):
            workspaces.setdefault(found.group(1), policy)
    return orgs, workspaces


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
        return str(policy.id)
    owners = {policy.id: container, **dict.fromkeys(_below_owned_by(iam, policy), container)}
    try:
        iam.move_policies(owners)
    except (ValueError, IAMConflictError) as exc:
        report.notes.append(
            f"{policy.id} ({policy.name}) stays {policy.owner_scope}'s, not {container}'s: {exc}"
        )
        return str(policy.id)
    report.moved[container] = sorted(owners)
    return str(policy.id)


def plan_and_apply(
    iam: Any,
    orgs: Mapping[str, str],
    workspaces: Mapping[str, tuple[str | None, str]],
    known: Mapping[str, DefaultsRecord],
) -> tuple[list[DefaultsRecord], Report]:
    """For each organization (``{id: name}``) and workspace (``{id: (org, name)}``)
    with no record yet, adopt what the sets' move made or make new defaults (what an
    earlier attempt made and did not record is found again, never made twice), then
    put the groups in step with the roles. As ``api``; pure of the database."""
    report = Report(notes=list(NOTES))
    missing_orgs = [o for o in sorted(orgs) if org_container(o) not in known]
    missing_workspaces = [
        w for w in sorted(workspaces) if workspace_container(workspaces[w][0], w) not in known
    ]
    if not missing_orgs and not missing_workspaces:
        return [], report
    org_made, workspace_made = made_by_move(iam)
    records: dict[str, DefaultsRecord] = dict(known)
    made: list[DefaultsRecord] = []
    for org_id in missing_orgs:
        container = org_container(org_id)
        try:
            adopted = org_made.get(org_id)
            record = make_org(iam, org_id, orgs[org_id], adopt=str(adopted.id) if adopted else None)
            (report.adopted if adopted else report.made).append(container)
            records[container] = record
            made.append(record)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"No access policy and groups for {container}")
            report.failed.append(f"{container}: {exc}")
    for workspace_id in missing_workspaces:
        org_id, label = workspaces[workspace_id]
        container = workspace_container(org_id, workspace_id)
        try:
            found = workspace_made.get(workspace_id)
            if found is not None:
                access = adopt_workspace_access(iam, found, container, report)
                record = make_workspace(iam, org_id, workspace_id, label, parent=None, adopt=access)
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
    holders = holders_by_container(iam) if made else {}
    for record in made:
        try:
            sync(iam, record, holders.get(record.container, {}))
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


MOVES = ("policy_tree_v1", "container_names_v1")


async def migrate(db: AsyncSession, defaults: ContainerDefaults = CONTAINER_DEFAULTS) -> Report:
    """Give every organization and workspace with none its access policy and default
    groups (adopting what the sets' move made), then record ``container_defaults_v1``
    once nothing failed. Runs at every start, after the moves, under their lock
    (``main``): only what has no record is touched, and nothing at all while a move is
    not recorded (it is the move that makes the access policies to adopt)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_names import recorded

    store = SqlDefaultsStore(db)
    for move in MOVES:
        if not await recorded(db, move):
            report = Report()
            report.notes.append(f"Waits for {move}: nothing made")
            return report
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
        defaults.remember(record)
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
    "moves_pending",
    "nothing_document",
    "role_holders",
    "sync",
]
