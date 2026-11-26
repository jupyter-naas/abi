"""Workspace settings > General › Features and Agents/Apps: what a workspace offers,
written into its access policy "<W> access" (``iam/workspace_offer``, ADR
``20261120_access_levels_and_groups``).

"<W> access" is the workspace's allow-list and its ceiling: a feature, an agent or
an app is offered in W when its section of "<W> access" names it. Everyone is the
feature in the ``OfferFeatures`` section, Nobody is the feature out of it: one
policy for the workspace, never a "Feature · X" policy per feature (those an older
version wrote stay listed among the other policies naming the feature, until the
access migration retires them). Who holds "<W> access" is its groups': today the
workspace's admins, then everyone in the workspace group (S2), each within what
their level gives. Only… is not a workspace setting any more: a group holding a
policy for the feature gives it to some people.

Its Files part gives what lies outside the workspace (``iam/given_files``, ADR
``20261125_offer_gives_outside_resources``): Organization, Platform and System Files,
each Off, Read or Read and write, as given sections of "<W> access". Whoever holds a
section may give it; a workspace's admin may narrow or remove one, never add it. Its
Graphs part (``iam/given_graphs``), written by Settings › Graphs: the graphs it is given
to read or write, every graph of its organization, and what it closes of its own.

Every write is an ordinary IAM call made as the caller and audited first
(``iam:UpdatePolicy`` on "<W> access"), so IAM's own rules apply: grant only what
you hold, within the organization's offer (its parent). On top of them a row
changes only for a caller who holds the feature there. Other policies naming the
feature are listed with it ("also granted / denied by"): a Deny of theirs still
wins.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import (
    CHOICES,
    FeatureChange,
    FeaturePolicyStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import given_files, given_graphs
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.given_files import (
    LABELS,
    MODES,
    OFF,
    ORDER,
    ORG_FILES,
    Mode,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import PLATFORM, nexus_resource, org_of
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    GRAPH_FIELDS,
    SECTIONS,
    WHOLE_MODULE,
    Offer,
    OrgFiles,
    offer_of,
    with_offer,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import IamGateway
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import run_audited
from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.services.iam.IAMPorts import (
    GrantableCatalog,
    IAMConflictError,
    IAMNotFoundError,
    IIAMService,
    PermissionDeniedError,
    Policy,
)
from naas_abi_core.services.iam.IAMService import attachment_resource, policy_resource
from naas_abi_core.services.iam.names import matches, substitute
from naas_abi_core.services.iam.policy import Statement
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

USE_FEATURE = "nexus:UseFeature"
AUDIT_SERVICE = "iam"
MAX_PRINCIPALS = 100
PRINCIPAL_PREFIXES = ("usr_", "grp_")
# Policies read at a workspace to find the others naming a feature.
MAX_POLICY_SCAN = 2000
# A chain is at most this deep (core's ``policy.MAX_DEPTH``).
MAX_CHAIN = 8

ContainerOf = Callable[[str], Awaitable[str | None]]
DefaultsOf = Callable[[str], Awaitable[Any]]
Features = Callable[[], Sequence[str]]


def feature_label(key: str) -> str:
    return key[:1].upper() + key[1:]


def _expands_to(pattern: str, resource: str, scope: str) -> bool:
    expanded = substitute(pattern, {"scope": scope, "principal.id": None, "user.id": None})
    return expanded is not None and matches(expanded, resource)


def names_feature(statement: Statement, resource: str, scope: str) -> bool:
    """Whether ``statement``, attached at ``scope``, names ``UseFeature`` on ``resource``."""
    return any(matches(a, USE_FEATURE) for a in statement.actions) and any(
        _expands_to(pattern, resource, scope) for pattern in statement.resources
    )


def offered(chain: Sequence[Policy], resource: str, scope: str) -> bool:
    """Whether a sub-policy of ``chain[0]`` attached at ``scope`` may grant the feature:
    an Allow of every policy of the chain names it and no Deny of theirs does."""
    if not chain:
        return False
    for policy in chain:
        statements = policy.document.statements
        if not any(s.effect == "Allow" and names_feature(s, resource, scope) for s in statements):
            return False
        if any(s.effect == "Deny" and names_feature(s, resource, scope) for s in statements):
            return False
    return True


def holds(
    grantable: Sequence[GrantableCatalog], resource: str, scope: str, action: str = USE_FEATURE
) -> bool:
    """Whether the caller may grant ``action`` (``UseFeature`` by default) on
    ``resource`` at ``scope`` (IAM's ``grantable``, what ``/publishers`` answers): they
    hold it there."""
    for catalog in grantable:
        for granted in catalog.actions:
            held = (
                granted.action if ":" in granted.action else f"{catalog.service}:{granted.action}"
            )
            if not matches(held, action):
                continue
            if any(_expands_to(p, resource, scope) for p in granted.resources) and not any(
                _expands_to(p, resource, scope) for p in granted.excluded
            ):
                return True
    return False


def holds_statements(grantable: Sequence[GrantableCatalog], statements: Sequence[dict]) -> bool:
    """Whether the caller holds every action of ``statements`` on each of their
    resources, at the platform (``grantable`` of ``abi:``): what IAM's held check of a
    given section asks. A resource pattern is matched as written (``abi:*`` holds
    ``abi:nexus:platform_file/*``), so it may say less than IAM would, never more."""
    return all(
        holds(grantable, resource, PLATFORM, action)
        for statement in statements
        for action in statement["actions"]
        for resource in statement["resources"]
    )


def _actor_id(user: Any) -> str:
    found = user if isinstance(user, str) else getattr(user, "id", None)
    if found:
        return str(found)
    named = current_call_context().user
    return named.id if named is not None else "unknown"


def _ref(policy: Policy) -> dict[str, Any]:
    return {"id": policy.id, "name": policy.name, "owner_scope": policy.owner_scope}


ONLY_REFUSED = (
    "Only… is not a workspace setting any more: {label} is offered to the whole "
    "workspace or to nobody. A group holding a policy for {label} gives it to some people."
)


def check_changes(changes: Sequence[FeatureChange], features: Sequence[str]) -> None:
    """Refuse (``ValueError``) a batch naming an unknown feature twice or at all, an
    unknown choice, or Only… with nobody (or something but users and groups)."""
    seen: set[str] = set()
    if not changes:
        raise ValueError("No change to save")
    for change in changes:
        if change.feature not in features:
            raise ValueError(f"{change.feature!r} is not a feature of this deployment")
        if change.feature in seen:
            raise ValueError(f"{feature_label(change.feature)} is changed twice")
        seen.add(change.feature)
        if change.choice not in CHOICES:
            raise ValueError(f"{change.choice!r} is not Everyone, Only… or Nobody")
        if change.choice == "only":
            if not change.principals:
                raise ValueError(f"Only…: choose who may use {feature_label(change.feature)}")
            if len(change.principals) > MAX_PRINCIPALS:
                raise ValueError(f"Only…: at most {MAX_PRINCIPALS} members and groups")
            if not all(p.startswith(PRINCIPAL_PREFIXES) for p in change.principals):
                raise ValueError("Only…: choose members and groups")
        elif change.principals:
            raise ValueError(f"{change.choice}: names nobody")


@dataclass(frozen=True)
class OfferChange:
    """Whether the workspace offers an agent, app, workflow or pipeline of a module
    (``kind``: ``agents``, ``apps``, ``workflows``, ``pipelines``; ``name`` ``*``
    for the whole module)."""

    kind: str
    module: str
    name: str
    offered: bool


def check_offer_changes(changes: Sequence[OfferChange]) -> None:
    if not changes:
        raise ValueError("No change to save")
    for change in changes:
        if change.kind not in SECTIONS:
            raise ValueError(f"{change.kind!r} is not agents, apps, workflows or pipelines")
        if not change.module.strip() or not change.name.strip():
            raise ValueError("Name the module and the item (* for the whole module)")


def _offer_json(offer: Offer) -> dict[str, Any]:
    return {
        **{
            kind: [{"module": m, "name": n} for m, n in sorted(offer.items(kind))]
            for kind in SECTIONS
        },
        "search_sources": sorted(offer.search_sources),
    }


def check_file_changes(changes: Mapping[str, str]) -> None:
    """Refuse (``ValueError``) no change, an unknown section or a mode it does not have."""
    if not changes:
        raise ValueError("Name a file section to change")
    for key, mode in changes.items():
        if key not in MODES:
            raise ValueError(f"{key!r} is not org_files, platform_files or system_files")
        if mode not in MODES[key]:
            raise ValueError(f"{LABELS[key]} is one of {', '.join(MODES[key])}, not {mode!r}")


def file_mode(offer: Offer, key: str) -> Mode:
    """The mode ``offer`` gives a file section (``off`` when it gives none)."""
    if key == ORG_FILES:
        return offer.org_files.mode if offer.org_files is not None else OFF
    return getattr(offer, key) or OFF


def with_file_mode(offer: Offer, key: str, mode: Mode, organization: str | None) -> Offer:
    """``offer`` giving the file section ``key`` in ``mode`` (``off``: not at all)."""
    if key == ORG_FILES:
        if mode != OFF and not organization:
            raise ValueError(
                "This workspace belongs to no organization: it has no Organization Files"
            )
        return replace(offer, org_files=OrgFiles(str(organization), mode) if mode != OFF else None)
    return replace(offer, **{key: mode if mode != OFF else None})


def _gives(key: str) -> str:
    if key == ORG_FILES:
        return "Only an admin of the organization or a platform admin gives Organization Files."
    return f"Only a platform admin gives {LABELS[key]}."


def file_rows(
    offer: Offer,
    *,
    organization: str | None,
    grantable: Sequence[GrantableCatalog],
    access: Policy | None,
    widen: bool,
) -> list[dict[str, Any]]:
    """The Files rows of the offer: each section's mode, the modes the caller may choose
    (any they hold, and any narrower than the current one) and why they may not change
    it. No Organization Files row for a workspace in no organization."""
    rows: list[dict[str, Any]] = []
    for key in MODES:
        if key == ORG_FILES and organization is None:
            continue
        mode = file_mode(offer, key)
        choices = [mode]
        if access is not None and widen:
            choices = [
                m
                for m in MODES[key]
                if given_files.narrower_or_equal(m, mode)
                or holds_statements(grantable, given_files.statements(key, m, organization))
            ]
        editable = len(choices) > 1
        reason: str | None = None
        if access is None:
            reason = "This workspace has no access policy yet."
        elif not widen:
            reason = f"IAM does not let you change {access.name}."
        elif not editable:
            reason = _gives(key)
        rows.append(
            {
                "key": key,
                "label": LABELS[key],
                "mode": mode,
                "modes": list(MODES[key]),
                "choices": sorted(choices, key=ORDER.index),
                "editable": editable,
                "reason": reason,
            }
        )
    return rows


def my_files_json() -> dict[str, str]:
    """My Files, a setting of the deployment (``feature_flags.viewer_my_files``):
    every Member writes theirs; Viewers read theirs, or have none."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.levels import viewer_my_files

    return {"members": "write", "viewers": "read" if viewer_my_files() else "none"}


def check_source_changes(changes: Mapping[str, bool]) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.search.sources import ALL_SOURCES

    if not changes:
        raise ValueError("Name a source to change")
    unknown = sorted(set(changes) - set(ALL_SOURCES))
    if unknown:
        raise ValueError(f"Not a search source: {', '.join(unknown)}")


class FeatureAccessService:
    def __init__(
        self,
        gateway: IamGateway,
        store: FeaturePolicyStore,
        audit: AdminAuditLog,
        *,
        container_of: ContainerOf,
        defaults_of: DefaultsOf,
        features: Features,
    ) -> None:
        self._gateway = gateway
        self._store = store
        self._audit = audit
        self._container_of = container_of
        self._defaults_of = defaults_of
        self._features = features

    # -- reading --------------------------------------------------------------------

    async def _where(self, workspace_id: str) -> tuple[str, Any]:
        container = await self._container_of(workspace_id)
        if container is None:
            raise IAMNotFoundError("Workspace not found")
        return container, await self._defaults_of(container)

    async def read(self, user: Any, workspace_id: str) -> dict[str, Any]:
        """Each enabled feature: whether the workspace offers it (Everyone) or not
        (Nobody), the other policies naming it there, whether its organization
        offers it, and whether the caller may change it."""
        container, record = await self._where(workspace_id)
        session = self._gateway.bind(user)
        features = list(self._features())
        return await run_in_threadpool(
            self._snapshot, session, workspace_id, container, record, features
        )

    def _chain(self, policy_id: str | None) -> list[Policy]:
        """The access policy and the policies above it, read as Nexus (the ceiling is
        shown to whoever may see the workspace's configuration)."""
        chain: list[Policy] = []
        while policy_id and len(chain) < MAX_CHAIN:
            policy = self._gateway.policy(policy_id)
            if policy is None:
                break
            chain.append(policy)
            policy_id = policy.parent_id
        return chain

    def _principal(self, principal_id: str) -> dict[str, Any]:
        record = self._gateway.principal(principal_id)
        kind = (
            record.kind
            if record is not None
            else ("group" if principal_id.startswith("grp_") else "user")
        )
        name = (record.display_name or record.name or record.email) if record is not None else None
        return {"id": principal_id, "kind": kind, "name": name or principal_id}

    @staticmethod
    def _policies_at(session: IIAMService, container: str) -> list[Policy]:
        found: list[Policy] = []
        after: str | None = None
        try:
            while len(found) < MAX_POLICY_SCAN:
                page = session.list_policies(after=after, scope=container)
                found += list(page.items)
                after = page.next_after
                if not after:
                    break
        except PermissionDeniedError:
            return []
        return found

    @staticmethod
    def _can(session: IIAMService, container: str, access_id: str | None) -> dict[str, bool]:
        any_policy = policy_resource("*", container)
        any_attachment = attachment_resource("*", "*", container)
        widen = (
            bool(access_id)
            and session.authorize(
                "iam:UpdatePolicy", policy_resource(str(access_id), container)
            ).allowed
        )
        return {
            "create": session.authorize("iam:CreatePolicy", any_policy).allowed,
            "attach": session.authorize("iam:AttachPolicy", any_attachment).allowed,
            "detach": session.authorize("iam:DetachPolicy", any_attachment).allowed,
            "widen": widen,
        }

    def _snapshot(
        self,
        session: IIAMService,
        workspace_id: str,
        container: str,
        record: Any,
        features: list[str],
    ) -> dict[str, Any]:
        access_id = getattr(record, "access_policy_id", None)
        members_id = getattr(record, "members_group_id", None)
        can = self._can(session, container, access_id)
        chain = self._chain(access_id)
        access = chain[0] if chain else None
        offer = offer_of(access.document) if access is not None else Offer()
        grantable = session.grantable(container)
        others = [
            p for p in self._policies_at(session, container) if not p.managed and p.id != access_id
        ]
        attached: dict[str, bool] = {}

        def is_attached(policy_id: str) -> bool:
            if policy_id not in attached:
                attached[policy_id] = bool(session.list_attachments(policy_id=policy_id))
            return attached[policy_id]

        rows = []
        for key in features:
            resource = nexus_resource("feature", container=container, id=key)
            also = []
            for other in others:
                effects = {
                    s.effect
                    for s in other.document.statements
                    if names_feature(s, resource, container)
                }
                if effects:
                    also.append(
                        {
                            **_ref(other),
                            "effect": "Deny" if "Deny" in effects else "Allow",
                            "attached": is_attached(other.id),
                        }
                    )
            rows.append(
                self._row(
                    key,
                    resource,
                    container,
                    access=access,
                    offer=offer,
                    can=can,
                    # What the organization offers (the chain above "<W> access");
                    # a workspace in none has nothing above it.
                    offered_here=offered(chain[1:], resource, container) if chain[1:] else True,
                    held=holds(grantable, resource, container),
                    also=also,
                )
            )
        return {
            "workspace_id": workspace_id,
            "scope": container,
            "access_policy": _ref(access) if access is not None else None,
            "members_group": self._principal(members_id) if members_id else None,
            "can": can,
            "features": rows,
        }

    @staticmethod
    def _row(
        key: str,
        resource: str,
        container: str,
        *,
        access: Policy | None,
        offer: Offer,
        can: dict[str, bool],
        offered_here: bool,
        held: bool,
        also: list[dict[str, Any]],
    ) -> dict[str, Any]:
        label = feature_label(key)
        in_section = key in offer.features
        # Allowed by "<W> access" otherwise than by its Features section (a ceiling
        # of an older version, a statement written on its page): shown, not rewritten.
        by_hand = access is not None and not in_section and offered([access], resource, container)
        choice = "everyone" if in_section or by_hand else "nobody"
        reason: str | None = None
        if access is None:
            reason = "This workspace has no access policy yet."
        elif by_hand:
            reason = f"{access.name} allows {label} on its policy page: change it there."
        elif not held:
            reason = f"You do not hold {label} here, so you cannot give it or take it back."
        elif not can["widen"]:
            reason = f"IAM does not let you change {access.name}."
        return {
            "key": key,
            "label": label,
            "choice": choice,
            "principals": [],
            "policy": _ref(access) if access is not None else None,
            "hand_edited": by_hand,
            "offered": offered_here,
            "held": held,
            "editable": reason is None,
            "reason": reason,
            "also": also,
        }

    # -- changing -------------------------------------------------------------------

    async def save(
        self, user: Any, workspace_id: str, changes: Sequence[FeatureChange]
    ) -> dict[str, Any]:
        """Apply each change, feature by feature, as the caller; a refused one is
        named in ``errors`` and the others still apply. Answers the state after."""
        container, record = await self._where(workspace_id)
        features = list(self._features())
        check_changes(changes, features)
        before = await self.read(user, workspace_id)
        rows = {row["key"]: row for row in before["features"]}
        errors: dict[str, str] = {}
        for change in changes:
            row = rows[change.feature]
            refusal = self._refusal(row, change, before)
            if refusal is not None:
                errors[change.feature] = refusal
                continue
            if (change.choice == "everyone") == (row["choice"] == "everyone"):
                continue
            try:
                await self._set_offer(
                    user,
                    workspace_id,
                    record.access_policy_id,
                    f"feature-access.{change.choice}",
                    f"{workspace_id}/{change.feature}",
                    lambda offer, key=change.feature, on=change.choice == "everyone": replace(
                        offer,
                        features=offer.features | {key} if on else offer.features - {key},
                    ),
                )
            except (PermissionDeniedError, IAMNotFoundError, IAMConflictError, ValueError) as exc:
                errors[change.feature] = str(exc)
        after = await self.read(user, workspace_id)
        return {**after, "errors": errors}

    @staticmethod
    def _refusal(row: dict[str, Any], change: FeatureChange, state: dict[str, Any]) -> str | None:
        if change.choice == "only":
            return ONLY_REFUSED.format(label=row["label"])
        if not row["editable"]:
            return row["reason"]
        if change.choice != "nobody" and not row["offered"]:
            return (
                f"{row['label']} is not offered in this workspace's organization: "
                "a platform administrator widens it first."
            )
        return None

    async def _set_offer(
        self,
        user: Any,
        workspace_id: str,
        access_id: str | None,
        operation: str,
        resource_id: str,
        change: Callable[[Offer], Offer],
        *,
        detail: str = "",
    ) -> None:
        """Rewrite the sections of "<W> access" as the caller, audited first: read
        again here, so a change made meanwhile is kept (and the revision checked)."""
        if not access_id:
            raise IAMNotFoundError("This workspace has no access policy yet")

        def write(session: IIAMService) -> None:
            policy = session.get_policy(access_id)
            wanted = change(offer_of(policy.document))
            session.update_policy(
                policy.id,
                expected_revision=policy.revision,
                document=with_offer(policy.document, wanted),
            )

        await self._change(user, operation, resource_id, write, detail=detail)
        AUTHZ.forget_offers()  # what the workspace's lists show (``filter_scopes``)

    # -- agents, apps, workflows and pipelines ----------------------------------------

    async def read_offer(self, user: Any, workspace_id: str) -> dict[str, Any]:
        """The agents, apps, workflows and pipelines "<W> access" offers by name (or
        whole module), and whether the caller may change them."""
        container, record = await self._where(workspace_id)
        access_id = getattr(record, "access_policy_id", None)
        session = self._gateway.bind(user)

        def snapshot() -> dict[str, Any]:
            access = self._gateway.policy(access_id) if access_id else None
            offer = offer_of(access.document) if access is not None else Offer()
            can = self._can(session, container, access_id)
            widen = access is not None and can["widen"]
            return {
                "workspace_id": workspace_id,
                "scope": container,
                "access_policy": _ref(access) if access is not None else None,
                "editable": widen,
                "whole_module": WHOLE_MODULE,
                "offered": _offer_json(offer),
                "files": file_rows(
                    offer,
                    organization=org_of(container),
                    # What the caller holds, given grants left out (IAM's ``grantable``).
                    grantable=session.grantable(PLATFORM) if widen else [],
                    access=access,
                    widen=widen,
                ),
                "my_files": my_files_json(),
                # Settings › Graphs edits it: shown here, not changed.
                "graphs": given_graphs.summary(offer),
            }

        return await run_in_threadpool(snapshot)

    async def save_offer(
        self, user: Any, workspace_id: str, changes: Sequence[OfferChange]
    ) -> dict[str, Any]:
        """Offer (or stop offering) each item, in one write of "<W> access" as the
        caller: IAM refuses an item the caller does not hold
        (``PermissionDeniedError``, 403) or one beyond the organization's offer
        (``ValueError``, 422), and then nothing changes."""
        check_offer_changes(changes)
        _container, record = await self._where(workspace_id)

        def apply(offer: Offer) -> Offer:
            items = {kind: set(offer.items(kind)) for kind in SECTIONS}
            for c in changes:
                (items[c.kind].add if c.offered else items[c.kind].discard)((c.module, c.name))
            return replace(offer, **{kind: frozenset(v) for kind, v in items.items()})

        detail = ",".join(
            f"{'+' if c.offered else '-'}{c.kind}:{c.module}/{c.name}" for c in changes
        )
        await self._set_offer(
            user,
            workspace_id,
            getattr(record, "access_policy_id", None),
            "workspace-offer.update",
            workspace_id,
            apply,
        )
        state = await self.read_offer(user, workspace_id)
        _log.info(f"Offer of {workspace_id} changed: {detail}")
        return state

    async def save_search_sources(
        self, user: Any, workspace_id: str, changes: Mapping[str, bool]
    ) -> dict[str, Any]:
        """Offer (or stop offering) search sources (``search.sources``), in one write
        of "<W> access" as the caller: as ``save_offer``, IAM refuses a source the
        caller does not hold (403) or one beyond the organization's offer (422)."""
        check_source_changes(changes)
        _container, record = await self._where(workspace_id)

        def apply(offer: Offer) -> Offer:
            on = {s for s, offered in changes.items() if offered}
            off = {s for s, offered in changes.items() if not offered}
            return replace(offer, search_sources=(offer.search_sources | on) - off)

        await self._set_offer(
            user,
            workspace_id,
            getattr(record, "access_policy_id", None),
            "workspace-offer.search-sources",
            workspace_id,
            apply,
        )
        detail = ",".join(f"{'+' if v else '-'}{k}" for k, v in sorted(changes.items()))
        _log.info(f"Search sources of {workspace_id} changed: {detail}")
        return await self.read_offer(user, workspace_id)

    async def set_files(
        self, user: Any, workspace_id: str, changes: Mapping[str, str]
    ) -> dict[str, Any]:
        """Give the workspace's people Organization, Platform or System Files
        (``{section: mode}``), in one write of "<W> access" as the caller: IAM refuses
        a section the change widens that the caller does not hold (403); narrowing or
        removing one needs only the right to change the policy. Answers the offer after."""
        check_file_changes(changes)
        container, record = await self._where(workspace_id)
        organization = org_of(container)
        if organization is None and changes.get(ORG_FILES, OFF) != OFF:
            raise ValueError(
                "This workspace belongs to no organization: it has no Organization Files"
            )

        def apply(offer: Offer) -> Offer:
            for key, mode in changes.items():
                offer = with_file_mode(offer, key, mode, organization)  # type: ignore[arg-type]
            return offer

        await self._set_offer(
            user,
            workspace_id,
            getattr(record, "access_policy_id", None),
            "workspace-offer.files",
            workspace_id,
            apply,
            detail=",".join(f"{k}={v}" for k, v in sorted(changes.items())),
        )
        _log.info(f"Files given by {workspace_id}: {dict(sorted(changes.items()))}")
        return await self.read_offer(user, workspace_id)

    async def set_ontologies(self, user: Any, workspace_id: str, refs: Sequence[str]) -> Offer:
        """The ontology files the workspace offers (Settings › Ontologies, by ref), in one
        write of "<W> access" as the caller: IAM refuses a file beyond the organization's
        offer (422) or one the caller does not hold (403). Answers the offer after."""
        wanted = frozenset(str(r).strip() for r in refs if str(r).strip())
        _container, record = await self._where(workspace_id)
        access_id = getattr(record, "access_policy_id", None)
        await self._set_offer(
            user,
            workspace_id,
            access_id,
            "workspace-offer.ontologies",
            workspace_id,
            lambda offer: replace(offer, ontologies=wanted),
        )
        _log.info(f"Ontologies of {workspace_id}: {len(wanted)} offered")
        policy = await run_in_threadpool(self._gateway.policy, access_id)
        return offer_of(policy.document)

    async def set_graphs(
        self,
        user: Any,
        workspace_id: str,
        config: Any,
        *,
        owned: Iterable[str] = (),
        name_of: given_graphs.NameOf = given_graphs.anywhere_names,
    ) -> Offer:
        """What the workspace is given of the graphs outside it, and what it closes of its
        own (Settings › Graphs: a ``WorkspaceGraphPolicyConfig``), in one write of "<W>
        access" as the caller. The graphs that stay keep their names; ``name_of`` names a
        new one (as IAM placed it), ``owned`` are the graphs the workspace owns. IAM
        refuses a graph the caller does not hold for what it is given
        (``PermissionDeniedError``, 403) and nothing changes; taking one away needs only
        the right to change the policy. Answers the offer after."""
        container, record = await self._where(workspace_id)
        access_id = getattr(record, "access_policy_id", None)
        owned = frozenset(owned)

        def apply(offer: Offer) -> Offer:
            current = {f: getattr(offer, f) for f in GRAPH_FIELDS}
            fields = given_graphs.fields_of(
                config, container=container, owned=owned, name_of=name_of, current=current
            )
            return replace(offer, **fields)

        summary = given_graphs.summary(
            given_graphs.fields_of(config, container=container, owned=owned)
        )
        detail = ",".join(f"{k}={v}" for k, v in summary.items())
        await self._set_offer(
            user,
            workspace_id,
            access_id,
            "workspace-offer.graphs",
            workspace_id,
            apply,
            detail=detail,
        )
        _log.info(f"Graphs of {workspace_id}: {detail}")
        policy = await run_in_threadpool(self._gateway.policy, access_id)
        return offer_of(policy.document)

    async def _change(
        self,
        user: Any,
        operation: str,
        resource_id: str,
        call: Callable[[IIAMService], Any],
        *,
        detail: str = "",
    ) -> Any:
        """An IAM change as the caller, audited first: no record, no change."""
        session = self._gateway.bind(user)
        action = AdminAction(_actor_id(user), AUDIT_SERVICE, operation, resource_id, detail)
        return await run_audited(self._audit, action, lambda: run_in_threadpool(call, session))

    # -- for Access › Policies --------------------------------------------------------

    async def managed_among(self, policy_ids: Sequence[str]) -> dict[str, str]:
        """``{policy id: feature}``: those an older version of General wrote
        ("Feature · X"), marked on Access › Policies until the access migration
        retires them."""
        return await self._store.managed_among(policy_ids)


__all__ = [
    "FeatureAccessService",
    "OfferChange",
    "check_changes",
    "check_file_changes",
    "check_offer_changes",
    "file_rows",
]
