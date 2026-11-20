"""Each organization and each workspace has its own access policy and default
groups (``AGENTS.md``, "Access policies and default groups"; levels as groups, #1585).

- **"<O> access"**, owned by the platform: what organization O may use. A new
  organization's allows nothing (``nothing_document``): the platform admin widens
  it. It is attached to "<O> admins" below the organization, so O's admins use what
  it allows in each of O's workspaces and derive policies from it.
- **"<W> access"**, owned by workspace W and a sub-policy of its organization's
  (with no parent for a workspace in no organization): what W offers, its allow-list
  (``workspace_offer``) and ceiling. It is held by "<W> workspace" at W: a **bound**
  (core IAM, "Bounds"), which grants nothing itself and bounds what each person's
  level gives at W. Policies made in W for its people are sub-policies of it.
- **"<W> workspace"**, owned by W, a **membership group** of W: W's people, where
  their level ("Viewers", "Members": ``levels``) applies through ``${my workspaces}``.
- **"<W> admins"**, owned by W, a membership group of W too: ``builtin.admin`` and
  "Workspace admin access" at ``${my workspaces}``, which reaches W alone (it is W's
  group) within W's bound.
- **"<O> admins"**, owned by O: "<O> access" below O, ``builtin.admin`` at O and below
  it (every workspace of O).
- **"<O> people"**, owned by O, a membership group of O: ``builtin.viewer`` and "Viewer
  access" at ``${my workspaces}``: the organization's people, at its own level too.

Who belongs where is these groups' membership (``MEMBERSHIPS``): nothing is attached
to a person. A container recorded before #1585 has the retired "<X> members" in place
of its membership group (``grouped`` is False): its roles stay attachments and its
groups follow them (``sync``) until the move of #1587 converts it.

IAM holds the policies and the groups; ``container_defaults`` (Nexus's table) says
which they are, by the container's IAM name (``members_group_id``: the membership
group). Everything here is written as ``api`` for no user: it follows a creation or
a change the route already authorized.

The upgrade (``migrate``, recorded in ``iam_migrations`` as ``container_defaults_v1``)
gives existing organizations and workspaces theirs once: the access policies the
sets' move made (``policy_tree``) are kept, a workspace's moved to the workspace
with what is below it that its organization owned (``iam.move_policies``), and
neither is held by a group, which would bound (or give) its people what the move
kept from them. Organizations and workspaces made after the sets' move get new ones.
The groups are made empty: nobody gains or loses access.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import LEVELS, Levels
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    org_below,
    org_container,
    org_of,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    in_offer_form,
    instances_only,
    offer_document,
    offer_of,
    with_offer,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    Policy,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.names import MY_CONTAINERS_SCOPE, PLATFORM
from naas_abi_core.services.iam.policy import POLICY_VERSION
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

MIGRATION_NAME = "container_defaults_v1"
ROLES = ("owner", "admin", "member", "viewer")
ADMIN_ROLES = frozenset({"owner", "admin"})
NOTHING_SID = "Nothing"

# The organization's id is part of it: names are not unique, and an access policy made
# before and never recorded is found again by owner, name and description
# (``_access_made_before``), never another organization's of the same name.
ORG_ACCESS = (
    "What organization {label} ({org_id}) may use. The platform administrators widen it; its "
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
    """The retired "<X> members" (before #1585): renamed with its container, never made."""
    return f"{label} members"


def workspace_name(label: str) -> str:
    return f"{label} workspace"


def people_name(label: str) -> str:
    return f"{label} people"


def membership_name(container: str, label: str) -> str:
    """The name of ``container``'s membership group: "<W> workspace", "<O> people"."""
    return people_name(label) if is_org_container(container) else workspace_name(label)


def admins_name(label: str) -> str:
    return f"{label} admins"


def access_template(container: str) -> str | None:
    """The description of ``container``'s access policy as made, ``{label}`` unfilled;
    None for a container that is neither an organization nor a workspace."""
    org_id = org_of(container)
    if is_org_container(container) and org_id:
        return ORG_ACCESS.replace("{org_id}", org_id)
    if is_workspace_container(container):
        return WORKSPACE_ACCESS if org_id else ORGLESS_WORKSPACE_ACCESS
    return None


def access_description(container: str, label: str) -> str:
    template = access_template(container)
    if template is None:
        raise ValueError(f"{container} is neither an organization nor a workspace")
    return template.replace("{label}", label)


def labels_in(template: str, text: str) -> tuple[str, ...] | None:
    """The labels ``text`` was made with from ``template``, one per ``{label}``; None
    when it was not made from it (a person rewrote it)."""
    pattern = "(.+?)".join(re.escape(part) for part in template.split("{label}"))
    found = re.fullmatch(pattern, text, flags=re.DOTALL)
    return found.groups() if found else None


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

    async def org_name(self, org_id: str) -> str | None:
        """The organization's name, to label defaults made for it late."""
        ...

    async def workspace_seed(self, workspace_id: str) -> tuple[str | None, Any] | None:
        """The workspace's slug and stored ``catalog_seed``, what its offer is made
        from (``workspace_offer.seeded_offer``); None when it has no row."""
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

    async def org_name(self, org_id: str) -> str | None:
        row = (
            await self.db.execute(
                text("SELECT name FROM organizations WHERE id = :o"), {"o": org_id}
            )
        ).first()
        return str(row[0]) if row and row[0] else None

    async def workspace_seed(self, workspace_id: str) -> tuple[str | None, Any] | None:
        row = (
            await self.db.execute(
                text("SELECT slug, catalog_seed FROM workspaces WHERE id = :w"),
                {"w": workspace_id},
            )
        ).first()
        if row is None:
            return None
        return (str(row[0]) if row[0] else None), _parsed_seed(row[1])

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


def _parsed_seed(raw: Any) -> dict[str, Any] | None:
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import parse_catalog_seed

    if raw is None or isinstance(raw, dict):
        return raw
    return parse_catalog_seed(str(raw))


def enabled_features() -> list[str]:
    """The deployment's enabled features: what a new workspace offers until its
    Features setting turns one off."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import enabled_feature_catalog
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    try:
        return list(enabled_feature_catalog(live_settings().feature_flags))
    except Exception:  # noqa: BLE001 - no settings: no feature offered
        logger.exception("The enabled features could not be read: a new workspace offers none")
        return []


def new_workspace_offer(slug: str | None, catalog_seed: dict[str, Any] | None) -> Offer:
    """What a new workspace offers: its seed's agents, apps and shared modules
    (``workspace_offer.seeded_offer``), and every enabled feature. The unresolved
    seed refs are logged."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import seeded_offer

    features = enabled_features()
    seeded = seeded_offer(slug, catalog_seed, features=features)
    if seeded is None:
        return Offer(features=frozenset(features))
    offer, unresolved = seeded
    if unresolved:
        logger.warning(
            f"Workspace {slug}: not offered, its module is not loaded: {', '.join(unresolved)}"
        )
    return offer


def widen_offer(iam: Any, policy_id: str | None, offer: Offer) -> bool:
    """Add ``offer`` to the allow-list ``policy_id`` (an "<O> access" or a
    "<W> access" in offer form): never removes. A ceiling of an older version
    (not in offer form) is left to the access migration. As ``api``; whether it
    changed."""
    if not policy_id or offer.is_empty():
        return False
    try:
        policy = iam.get_policy(policy_id)
    except (IAMNotFoundError, ResourceNotFoundError):
        return False
    if not in_offer_form(policy.document):
        logger.info(f"{policy_id} ({policy.name}) is no allow-list yet: the access migration's")
        return False
    held = offer_of(policy.document)
    wanted = held.merged(offer)
    if wanted == held:
        return False
    iam.update_policy(
        policy.id,
        expected_revision=policy.revision,
        document=with_offer(policy.document, wanted),
    )
    return True


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


# Policies by ``(owner, name, description)``: what finds an access policy made before.
MadeBefore = Mapping[tuple[str, str, str], str]


def index_made_before(policies: Sequence[Policy]) -> dict[tuple[str, str, str], str]:
    """``MadeBefore`` of ``policies``, the first of each kind kept."""
    found: dict[tuple[str, str, str], str] = {}
    for policy in policies:
        found.setdefault(
            (str(policy.owner_scope), str(policy.name), str(policy.description)), str(policy.id)
        )
    return found


def _access_made_before(
    iam: Any,
    owner: str,
    name: str,
    description: str,
    *,
    scope: str | None,
    made_before: MadeBefore | None = None,
) -> str | None:
    """An access policy an earlier attempt made and never recorded (it stopped
    before its record was written): found by owner, name and description, in
    ``made_before`` when the caller indexed the policies once (the start-up pass),
    else by listing them."""
    if made_before is not None:
        return made_before.get((owner, name, description))
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


def _membership_group(iam: Any, container: str, group_id: str | None) -> str | None:
    """``group_id``, a group of ``container`` made a membership group of it when it
    is not yet one; None for none."""
    if group_id is None:
        return None
    group = iam.get_group(group_id)
    if group.membership_of != container:
        iam.mark_group(group_id, membership_of=container, level=bool(group.level_group))
    return group_id


def group_attachments(
    container: str, record: DefaultsRecord, levels: Levels, *, access: bool
) -> list[tuple[str, str, str | None]]:
    """``(policy, group, scope)`` the groups of ``record`` hold (``access``: with the
    access policy, which an adopted one is not, "The upgrade")."""
    membership, admins, policy = (
        record.members_group_id,
        record.admins_group_id,
        record.access_policy_id,
    )
    assert membership and admins and policy
    found: list[tuple[str, str, str | None]] = []
    if is_org_container(container):
        below = org_below(org_of(container) or "")
        if access:
            found.append((policy, admins, below))
        found += [
            (roles.ADMIN, admins, container),
            (roles.ADMIN, admins, below),
            (roles.VIEWER, membership, MY_CONTAINERS_SCOPE),
            (levels.viewer_access, membership, MY_CONTAINERS_SCOPE),
        ]
    else:
        if access:
            found.append((policy, membership, container))  # W's bound
        found += [
            (roles.ADMIN, admins, MY_CONTAINERS_SCOPE),
            (levels.workspace_admin_access, admins, MY_CONTAINERS_SCOPE),
        ]
    return found


def _ensure(
    iam: Any,
    *,
    container: str,
    label: str,
    access: str | None,
    make_access: Callable[[], str],
    find_access: Callable[[], str | None],
    adopted: bool,
) -> DefaultsRecord:
    """The access policy (``access``, else one made before and unrecorded, else a new
    one), the membership and admins groups (found by name, else made; a workspace's
    admins group is a membership group of it too) and what they hold
    (``group_attachments``; not the access policy when ``adopted``). On a failure, what
    this call made is taken back."""
    made: list[tuple[str, Any]] = []
    try:
        levels = LEVELS.get(iam)
        if access is None:
            access = find_access()
        if access is None:
            access = make_access()
            made.append(("policy", access))
        groups = _own_groups(iam, container)
        workspace = is_workspace_container(container)
        ids: list[str] = []
        for name, marked in (
            (membership_name(container, label), True),
            (admins_name(label), workspace),
        ):
            group_id = groups.get(name)
            if group_id is None:
                group_id = str(
                    iam.create_group(
                        name, scope=container, membership_of=container if marked else None
                    ).id
                )
                made.append(("group", group_id))
            elif marked:
                _membership_group(iam, container, group_id)
            ids.append(group_id)
        record = DefaultsRecord(container, access, ids[0], ids[1])
        held: dict[str, set[tuple[str, str | None]]] = {}
        for policy_id, group_id, scope in group_attachments(
            container, record, levels, access=not adopted
        ):
            if group_id not in held:
                held[group_id] = {
                    (a.policy_id, a.scope) for a in iam.list_attachments(principal_id=group_id)
                }
            if (policy_id, scope) not in held[group_id]:
                iam.attach_policy(policy_id, group_id, scope)
                made.append(("attachment", (policy_id, group_id, scope)))
    except Exception:
        _undo(iam, made)
        raise
    return record


def grouped(iam: Any, record: DefaultsRecord) -> bool:
    """Whether ``record``'s container keeps its people in groups (#1585): its
    membership group is one of it. False for one recorded before (its "<X>
    members"), whose roles are attachments until #1587 converts it. As ``api``."""
    if not record.members_group_id:
        return False
    try:
        group = iam.get_group(record.members_group_id)
    except (IAMNotFoundError, ResourceNotFoundError):
        return False
    return group.status != "deleted" and group.membership_of == record.container


def make_org(
    iam: Any,
    org_id: str,
    label: str,
    *,
    adopt: str | None = None,
    made_before: MadeBefore | None = None,
) -> DefaultsRecord:
    """ "<O> access" (the platform's, allowing nothing) attached to "<O> admins"
    below the organization, and the two groups; with ``adopt``, that policy instead,
    attached to nothing. Idempotent, and a failure leaves nothing. As ``api``."""
    name, description = access_name(label), access_description(org_container(org_id), label)
    return _ensure(
        iam,
        container=org_container(org_id),
        label=label,
        access=adopt,
        make_access=lambda: str(
            iam.create_policy(name, nothing_document(), description=description).id
        ),
        find_access=lambda: _access_made_before(
            iam, PLATFORM, name, description, scope=None, made_before=made_before
        ),
        adopted=adopt is not None,
    )


def make_workspace(
    iam: Any,
    org_id: str | None,
    workspace_id: str,
    label: str,
    *,
    parent: str | None,
    adopt: str | None = None,
    made_before: MadeBefore | None = None,
    offer: Offer | None = None,
) -> DefaultsRecord:
    """ "<W> access" (the workspace's, a sub-policy of ``parent``: the
    organization's access) attached to "<W> admins" at the workspace, and the two
    groups; with ``adopt``, that policy instead, attached to nothing. The access
    policy is the allow-list of ``offer`` (``workspace_offer``): what the workspace
    offers, by name; nothing without one. Idempotent, and a failure leaves nothing.
    As ``api``."""
    container = workspace_container(org_id, workspace_id)
    name, description = access_name(label), access_description(container, label)
    document = offer_document(offer) if offer is not None else nothing_document()
    return _ensure(
        iam,
        container=container,
        label=label,
        access=adopt,
        make_access=lambda: str(
            iam.create_policy(
                name, document, description=description, scope=container, parent=parent
            ).id
        ),
        find_access=lambda: _access_made_before(
            iam, container, name, description, scope=container, made_before=made_before
        ),
        adopted=adopt is not None,
    )


def make_org_late(iam: Any, org_id: str, label: str) -> DefaultsRecord:
    """``make_org`` for an organization the start-up pass has not seen yet: adopting
    the "<O> access" the sets' move made for it, as ``plan_and_apply`` would, rather
    than making a second one beside it. As ``api``."""
    adopted = made_by_move(iam)[0].get(org_id)
    return make_org(iam, org_id, label, adopt=str(adopted.id) if adopted else None)


def forget_made(iam: Any, record: DefaultsRecord) -> None:
    """Take back the IAM side of a record that could not be written (its groups, its
    access policy). As ``api``."""
    made: list[tuple[str, Any]] = []
    if record.access_policy_id:
        made.append(("policy", record.access_policy_id))
    for group in (record.members_group_id, record.admins_group_id):
        if group:
            made.append(("group", group))
    for group in (record.members_group_id, record.admins_group_id):
        for attachment in iam.list_attachments(principal_id=group) if group else []:
            made.append(("attachment", (attachment.policy_id, group, attachment.scope)))
    _undo(iam, made)


def align_names(
    iam: Any,
    record: DefaultsRecord,
    label: str,
    *,
    previous: Sequence[str] = (),
    policy: Policy | None = None,
) -> list[str]:
    """Name the access policy and the two groups of ``record`` after ``label``, its
    container's name now, as ``make_org`` and ``make_workspace`` would. Only what the
    system made is renamed: a name (or the description) made from an older label,
    ``previous`` (the name before a rename) or one the access policy's description,
    as made, still carries. A name a person chose stays. Idempotent. As ``api``;
    ``policy``, the access policy when the caller listed it. What changed."""
    template = access_template(record.container)
    if policy is None and record.access_policy_id:
        try:
            policy = iam.get_policy(record.access_policy_id)
        except (IAMNotFoundError, ResourceNotFoundError):
            policy = None
    described = labels_in(template, policy.description) if policy and template else None
    older = {*previous, *(described or ())} - {label}
    if not older:
        return []
    changed: list[str] = []

    def membership(label: str) -> str:
        return membership_name(record.container, label)

    for group_id, names_of in (
        (record.members_group_id, (members_name, membership)),
        (record.admins_group_id, (admins_name,)),
    ):
        if not group_id:
            continue
        try:
            group = iam.get_group(group_id)
        except IAMNotFoundError:
            continue
        if group.status == "deleted":
            continue
        for name_of in names_of:
            if group.name in {name_of(o) for o in older}:
                iam.update_group(group_id, name=name_of(label))
                changed.append(f"{group.name!r} -> {name_of(label)!r}")
                break
    if policy is not None and template is not None:
        updates: dict[str, str] = {}
        if policy.name in {access_name(o) for o in older}:
            updates["name"] = access_name(label)
        if described is not None and policy.description != access_description(
            record.container, label
        ):
            updates["description"] = access_description(record.container, label)
        if updates:
            iam.update_policy(policy.id, expected_revision=policy.revision, **updates)
            changed += [f"{getattr(policy, k)!r} -> {v!r}" for k, v in updates.items()]
    return changed


def align_all(
    iam: Any,
    orgs: Mapping[str, str],
    workspaces: Mapping[str, tuple[str | None, str]],
    records: Mapping[str, DefaultsRecord],
) -> list[str]:
    """``align_names`` for every recorded organization (``{id: name}``) and workspace
    (``{id: (org, name)}``) after its name in Nexus: what a rename made before names
    followed, or while they could not, is repaired at the next start. A failure is
    logged and the others go on. As ``api``; what changed, by container."""
    labels = {org_container(o): name for o, name in orgs.items()}
    labels.update({workspace_container(org, w): name for w, (org, name) in workspaces.items()})
    policies = {str(p.id): p for p in _pages(iam.list_policies)}
    changed: list[str] = []
    for container, record in sorted(records.items()):
        label = labels.get(container)
        if label is None:
            continue
        try:
            policy = policies.get(str(record.access_policy_id))
            changed += [
                f"{container}: {change}"
                for change in align_names(iam, record, label, policy=policy)
            ]
        except Exception:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"The access policy and groups of {container} keep their names")
    return changed


Holders = dict[str, set[str]]


def is_user(principal_id: str) -> bool:
    """Roles are for users (``usr_`` ids): never a group or a service account."""
    return principal_id.startswith("usr_")


def holders_by_container(iam: Any) -> dict[str, Holders]:
    """``{container: {user principal: {role}}}``: who holds a built-in role at each
    container itself (an org-wide mirror below an organization is not "at" it), as
    ``MEMBERSHIPS.members`` reads it, the role the highest they hold."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    return {
        where: {m.principal_id: {m.role} for m in members if is_user(m.principal_id)}
        for where, members in MEMBERSHIPS.members_by_scope(iam).items()
    }


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
    _grouped: dict[str, bool] = field(default_factory=dict)

    def remember(self, record: DefaultsRecord) -> None:
        self._known[record.container] = record
        self._missing.pop(record.container, None)
        self._grouped.pop(record.container, None)

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
        """None with no store, or while the moves are pending. A workspace's access is a
        sub-policy of its organization's: an organization with no record yet (made
        while the moves were pending, or whose defaults failed) gets its own first,
        the sets' move's "<O> access" when there is one."""
        if store is None or moves_pending():
            return None
        parent = None
        org_record = None
        if org_id:
            org_record = await store.get(org_container(org_id))
            if org_record is None:
                org_label = await store.org_name(org_id) or org_id
                org_record = await self._record(
                    store, lambda iam: make_org_late(iam, org_id, org_label)
                )
            parent = org_record.access_policy_id
        # A workspace in an organization offers its seed and the enabled features,
        # bounded by the organization's offer (its parent): the creator's picks never
        # reach beyond it. One in none has no parent to bound it: it offers nothing
        # until the platform administrators widen it, as before.
        offer = None
        if org_id:
            seed_of = getattr(store, "workspace_seed", None)
            seed = await seed_of(workspace_id) if callable(seed_of) else None
            offer = new_workspace_offer(*(seed or (None, None)))
        return await self._record(
            store,
            lambda iam: make_workspace(
                iam, org_id, workspace_id, label, parent=parent, offer=offer
            ),
        )

    async def dropped(self, store: DefaultsStore | None, container: str) -> None:
        """After IAM deleted the container (with what it owned): forget its records
        and, for an organization, delete its access policy, the platform's."""
        record = self._known.get(container)
        if record is None and store is not None:
            record = await store.get(container)
        for known in [c for c in self._known if c == container or c.startswith(container + "/")]:
            del self._known[known]
            self._grouped.pop(known, None)
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

    async def renamed(
        self, store: DefaultsStore | None, container: str, label: str, *, previous: str
    ) -> None:
        """After the container was renamed from ``previous`` to ``label``: its access
        policy and groups follow (``align_names``). Never fails the rename: a failure
        is logged, and the next start repairs it (``migrate``)."""
        if label == previous:
            return
        try:
            record = self._known.get(container)
            if record is None and store is not None:
                record = await store.get(container)
            if record is None:
                record = await self.record_of(container)
            if record is None:
                return
            found = record
            changed = await run_in_threadpool(
                lambda: _as_api(lambda iam: align_names(iam, found, label, previous=(previous,)))
            )
            for change in changed:
                logger.info(f"Renamed with {container}: {change}")
        except Exception:  # noqa: BLE001 - the rename stands; the names follow at the next start
            logger.exception(f"The access policy and groups of {container} keep their names")

    async def is_grouped(self, record: DefaultsRecord) -> bool:
        """``grouped`` of ``record``, remembered (a record's groups never change
        kind, but for the access move, which forgets what it converts)."""
        known = self._grouped.get(record.container)
        if known is None:
            known = await run_in_threadpool(lambda: _as_api(lambda iam: grouped(iam, record)))
            self._grouped[record.container] = known
        return known

    async def grouped_record(self, container: str) -> DefaultsRecord | None:
        """The record of ``container`` when its people are in groups (#1585); None
        for a container with no record or one recorded before (roles as
        attachments)."""
        if not (is_org_container(container) or is_workspace_container(container)):
            return None
        record = await self.record_of(container)
        if record is None or not await self.is_grouped(record):
            return None
        return record

    def forget_grouped(self, container: str | None = None) -> None:
        """Read the kind of ``container``'s groups (every one's) again."""
        if container is None:
            self._grouped.clear()
        else:
            self._grouped.pop(container, None)

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
            if record is None or await self.is_grouped(record):
                return  # its groups are the memberships themselves
            from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

            holders: Holders = {
                m.principal_id: {m.role}
                for m in await MEMBERSHIPS.members(scope)
                if is_user(m.principal_id)
            }
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
    reparented: list[str] = field(default_factory=list)
    # Access policies a configured workspace's seed added to (its own and its
    # organization's allow-lists).
    offered: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


_ORG_MADE = re.compile(r"^What organization (\S+) uses:")
_WORKSPACE_MADE = re.compile(r"^What workspace (\S+) uses, within its organization's:")


def made_by_move(
    iam: Any,
    policies: Sequence[Policy] | None = None,
    *,
    workspaces: Mapping[str, tuple[str | None, str]] | None = None,
) -> tuple[dict[str, Policy], dict[str, Policy]]:
    """The access policies the sets' move made, by organization and by workspace id,
    among ``policies`` (every one, listed, by default).

    A description is free text anyone who may write a policy chooses, so it only
    names a candidate: the move made an organization's at the platform, and a
    workspace's (``workspaces``: ``{id: (org, name)}``) owned by that workspace's
    own organization, or by the platform for one in none (or by the workspace, once
    adopted). Any other owner's is not that workspace's, whatever it says. Of two
    candidates, the older is kept."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree import (
        made_by_move as by_move,
    )

    orgs: dict[str, Policy] = {}
    found_workspaces: dict[str, Policy] = {}

    def keep(into: dict[str, Policy], key: str, policy: Policy) -> None:
        held = into.get(key)
        if held is None or _made_at(policy) < _made_at(held):
            into[key] = policy

    for policy in policies if policies is not None else _pages(iam.list_policies):
        if not by_move(policy):
            continue
        description = str(policy.description)
        if (found := _ORG_MADE.match(description)) and policy.owner_scope == PLATFORM:
            keep(orgs, found.group(1), policy)
        elif (found := _WORKSPACE_MADE.match(description)) and workspaces is not None:
            workspace_id = found.group(1)
            if workspace_id not in workspaces:
                continue
            org_id = workspaces[workspace_id][0]
            owners = {
                org_container(org_id) if org_id else PLATFORM,
                workspace_container(org_id, workspace_id),
            }
            if policy.owner_scope in owners:
                keep(found_workspaces, workspace_id, policy)
    return orgs, found_workspaces


def _made_at(policy: Policy) -> tuple[int, str]:
    created = getattr(policy, "created_at", None)
    return (0, created.isoformat()) if created is not None else (1, str(policy.id))


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


def apply_seeded_offers(
    iam: Any,
    workspaces: Mapping[str, tuple[str | None, str]],
    records: Mapping[str, DefaultsRecord],
    offers: Mapping[str, Offer],
    report: Report,
) -> None:
    """A configured workspace's seed (``offers``: ``{workspace id: Offer}``, the
    configuration's own entries) is in its allow-list and its organization's:
    what it names is added, never removed (as the seeds' app rows: what a person
    turned off is offered again at the next start while the configuration names
    it). The features are added to the organization's only: the workspace's are
    its Features setting's (its own were set when it was made). A ceiling of an
    older version is left to the access migration. As ``api``."""
    by_org: dict[str, Offer] = {}
    for workspace_id, offer in sorted(offers.items()):
        if workspace_id not in workspaces:
            continue
        org_id = workspaces[workspace_id][0]
        record = records.get(workspace_container(org_id, workspace_id))
        try:
            if record is not None and widen_offer(
                iam, record.access_policy_id, instances_only(offer)
            ):
                report.offered.append(record.container)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"The seed of {workspace_id} is not in its access policy")
            report.failed.append(f"{workspace_id}: {exc}")
        if org_id:
            by_org[org_id] = by_org.get(org_id, Offer()).merged(offer)
    for org_id, offer in sorted(by_org.items()):
        record = records.get(org_container(org_id))
        try:
            if record is not None and widen_offer(iam, record.access_policy_id, offer):
                report.offered.append(record.container)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"The seeds of {org_id}'s workspaces are not in its access policy")
            report.failed.append(f"{org_id}: {exc}")


def plan_and_apply(
    iam: Any,
    orgs: Mapping[str, str],
    workspaces: Mapping[str, tuple[str | None, str]],
    known: Mapping[str, DefaultsRecord],
    offers: Mapping[str, Offer] | None = None,
) -> tuple[list[DefaultsRecord], Report]:
    """For each organization (``{id: name}``) and workspace (``{id: (org, name)}``)
    with no record yet, adopt what the sets' move made or make new defaults (what an
    earlier attempt made and did not record is found again, never made twice), then
    put the groups in step with the roles. A configured workspace (``offers``) is
    made with its seed's allow-list, and its seed added to its organization's and
    its own (``apply_seeded_offers``). As ``api``; pure of the database."""
    offers = offers or {}
    report = Report(notes=list(NOTES))
    missing_orgs = [o for o in sorted(orgs) if org_container(o) not in known]
    missing_workspaces = [
        w for w in sorted(workspaces) if workspace_container(workspaces[w][0], w) not in known
    ]
    if not missing_orgs and not missing_workspaces:
        reparent_workspace_access(iam, workspaces, known, report)
        apply_seeded_offers(iam, workspaces, known, offers, report)
        return [], report
    # Every policy, listed once: what the move made, and what an attempt made before.
    policies = _pages(iam.list_policies)
    org_made, workspace_made = made_by_move(iam, policies, workspaces=workspaces)
    made_before = index_made_before(policies)
    records: dict[str, DefaultsRecord] = dict(known)
    made: list[DefaultsRecord] = []
    for org_id in missing_orgs:
        container = org_container(org_id)
        try:
            adopted = org_made.get(org_id)
            record = make_org(
                iam,
                org_id,
                orgs[org_id],
                adopt=str(adopted.id) if adopted else None,
                made_before=made_before,
            )
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
                    made_before=made_before,
                    offer=offers.get(workspace_id),
                )
                report.made.append(container)
            records[container] = record
            made.append(record)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"No access policy and groups for {container}")
            report.failed.append(f"{container}: {exc}")
    reparent_workspace_access(iam, workspaces, records, report)
    apply_seeded_offers(iam, workspaces, records, offers, report)
    # The groups are made empty (#1585): who belongs where is theirs from now on, and
    # the roles held before stay attachments until the access move (#1587).
    return made, report


def reparent_workspace_access(
    iam: Any,
    workspaces: Mapping[str, tuple[str | None, str]],
    records: Mapping[str, DefaultsRecord],
    report: Report,
) -> None:
    """Put each recorded "<W> access" of a workspace in an organization that has no
    parent under its organization's access, once that is recorded: one made while
    the organization had no record (an earlier version made it so) is bounded by
    the organization from then on. As ``api``."""
    for workspace_id, (org_id, _label) in sorted(workspaces.items()):
        if not org_id:
            continue
        record = records.get(workspace_container(org_id, workspace_id))
        org_record = records.get(org_container(org_id))
        if record is None or not record.access_policy_id:
            continue
        if org_record is None or not org_record.access_policy_id:
            continue
        try:
            policy = iam.get_policy(record.access_policy_id)
            if policy.parent_id is not None:
                continue
            iam.update_policy(
                policy.id, expected_revision=policy.revision, parent=org_record.access_policy_id
            )
            report.reparented.append(record.container)
        except Exception as exc:  # noqa: BLE001 - the others go on; this one at the next start
            logger.exception(f"The access of {record.container} is not under its organization's")
            report.failed.append(f"{record.container}: {exc}")


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


async def configured_offers(db: AsyncSession) -> dict[str, Offer]:
    """``{workspace id: Offer}`` of the workspaces the configuration seeds
    (``nexus_config.organizations[].workspaces[]``, by slug): their agents, apps
    and shared modules, and the enabled features. Only the configuration's own
    entries: a ``catalog_seed`` a creator stored is not the platform's to widen
    an organization with."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import _yaml_seed
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
        engine_agent_resolver,
        seeded_offer,
    )

    rows = (await db.execute(text("SELECT id, slug FROM workspaces"))).all()
    configured = [(str(w), str(slug)) for w, slug in rows if slug and _yaml_seed(str(slug))]
    if not configured:
        return {}
    features = enabled_features()
    resolve = engine_agent_resolver()
    offers: dict[str, Offer] = {}
    for workspace_id, slug in configured:
        seeded = seeded_offer(slug, None, features=features, resolve_agent=resolve)
        if seeded is None:
            continue
        offer, unresolved = seeded
        if unresolved:
            logger.warning(
                f"Workspace {slug}: not offered, its module is not loaded: {', '.join(unresolved)}"
            )
        offers[workspace_id] = offer
    return offers


async def migrate(db: AsyncSession, defaults: ContainerDefaults = CONTAINER_DEFAULTS) -> Report:
    """Give every organization and workspace with none its access policy and default
    groups (adopting what the sets' move made), then record ``container_defaults_v1``
    once nothing failed. Runs at every start, after the moves, under their lock
    (``main``): only what has no record is made, and nothing at all while a move is
    not recorded (it is the move that makes the access policies to adopt). Every
    recorded one's names then follow its container's (``align_all``)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_names import recorded

    store = SqlDefaultsStore(db)
    for move in MOVES:
        if not await recorded(db, move):
            report = Report()
            report.notes.append(f"Waits for {move}: nothing made")
            return report
    orgs, workspaces = await read_nexus(db)
    known = {record.container: record for record in await store.all()}
    offers = await configured_offers(db)
    made, report = await run_in_threadpool(
        lambda: _as_api(lambda iam: plan_and_apply(iam, orgs, workspaces, known, offers))
    )
    for record in made:
        await store.put(record)
    records = {**known, **{record.container: record for record in made}}
    try:
        renamed = await run_in_threadpool(
            lambda: _as_api(lambda iam: align_all(iam, orgs, workspaces, records))
        )
    except Exception:  # noqa: BLE001 - the names follow at the next start
        logger.exception("Access policies and default groups not named after their containers")
        renamed = []
    for change in renamed:
        logger.info(f"Named after its container: {change}")
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
    for container in report.reparented:
        logger.info(f"The access of {container} is now a sub-policy of its organization's")
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
    "access_description",
    "access_name",
    "admins_name",
    "align_all",
    "align_names",
    "defaults_store_of",
    "make_org",
    "make_workspace",
    "grouped",
    "group_attachments",
    "members_name",
    "membership_name",
    "people_name",
    "workspace_name",
    "apply_seeded_offers",
    "configured_offers",
    "migrate",
    "moves_pending",
    "new_workspace_offer",
    "nothing_document",
    "sync",
    "widen_offer",
]
