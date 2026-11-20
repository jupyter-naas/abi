"""Workspace settings > General › Features: who may use each feature of a workspace,
written as policies (``port.py``).

Each feature gets one policy "Feature · <name>", owned by the workspace, a sub-policy
of "<W> access" (the ceiling: it never grants what the workspace does not offer),
allowing ``nexus:UseFeature`` on that feature alone. Everyone is that policy attached
to "<W> members" at the workspace (a newcomer joins the group, so holds it), Only… to
the users and groups chosen there, Nobody to none. Every write is an ordinary IAM call
made as the caller and audited first, so IAM's own rules apply (grant only what you
hold, derive only from a policy you hold); on top of them a row changes only for a
caller who holds the feature there. Other policies naming the feature are listed with
it ("also granted / denied by"): a Deny of theirs still wins. One changed by hand on
its policy page is shown, never rewritten.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import (
    CHOICES,
    FeatureChange,
    FeaturePolicyStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource, scoped_resource
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
from naas_abi_core.services.iam.policy import POLICY_VERSION, Statement
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

USE_FEATURE = "nexus:UseFeature"
AUDIT_SERVICE = "iam"
SID = "UseFeature"
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


def policy_name(key: str) -> str:
    return f"Feature · {feature_label(key)}"


def policy_description(key: str) -> str:
    return (
        f"Who may use {feature_label(key)} in this workspace, set from its Settings › "
        "General › Features. Changed here, General shows it read-only."
    )


def feature_document(key: str) -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "statements": [
            {
                "sid": SID,
                "effect": "Allow",
                "actions": [USE_FEATURE],
                "resources": [scoped_resource("feature", key)],
            }
        ],
    }


def _expands_to(pattern: str, resource: str, scope: str) -> bool:
    expanded = substitute(pattern, {"scope": scope, "principal.id": None, "user.id": None})
    return expanded is not None and matches(expanded, resource)


def names_feature(statement: Statement, resource: str, scope: str) -> bool:
    """Whether ``statement``, attached at ``scope``, names ``UseFeature`` on ``resource``."""
    return any(matches(a, USE_FEATURE) for a in statement.actions) and any(
        _expands_to(pattern, resource, scope) for pattern in statement.resources
    )


def as_written(policy: Policy, key: str, container: str, parent: str | None) -> bool:
    """Whether the policy is still what General writes for ``key``: one Allow of
    ``UseFeature`` on the feature, owned by the workspace, below its access policy."""
    statements = [
        (s.effect, tuple(s.actions), tuple(s.resources)) for s in policy.document.statements
    ]
    return (
        statements == [("Allow", (USE_FEATURE,), (scoped_resource("feature", key),))]
        and policy.owner_scope == container
        and policy.parent_id == parent
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


def holds(grantable: Sequence[GrantableCatalog], resource: str, scope: str) -> bool:
    """Whether the caller may grant ``UseFeature`` on ``resource`` at ``scope``
    (IAM's ``grantable``, what ``/publishers`` answers): they hold it there."""
    for catalog in grantable:
        for granted in catalog.actions:
            action = (
                granted.action if ":" in granted.action else f"{catalog.service}:{granted.action}"
            )
            if not matches(action, USE_FEATURE):
                continue
            if any(_expands_to(p, resource, scope) for p in granted.resources) and not any(
                _expands_to(p, resource, scope) for p in granted.excluded
            ):
                return True
    return False


def _actor_id(user: Any) -> str:
    found = user if isinstance(user, str) else getattr(user, "id", None)
    if found:
        return str(found)
    named = current_call_context().user
    return named.id if named is not None else "unknown"


def _ref(policy: Policy) -> dict[str, Any]:
    return {"id": policy.id, "name": policy.name, "owner_scope": policy.owner_scope}


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
        """Each enabled feature with who may use it in the workspace, the other
        policies naming it there, the ceiling, and whether the caller may change it."""
        container, record = await self._where(workspace_id)
        known = await self._store.policies(workspace_id)
        session = self._gateway.bind(user)
        features = list(self._features())
        return await run_in_threadpool(
            self._snapshot, session, workspace_id, container, record, features, known
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

    def _snapshot(
        self,
        session: IIAMService,
        workspace_id: str,
        container: str,
        record: Any,
        features: list[str],
        known: dict[str, str],
    ) -> dict[str, Any]:
        access_id = getattr(record, "access_policy_id", None)
        members_id = getattr(record, "members_group_id", None)
        any_policy = policy_resource("*", container)
        any_attachment = attachment_resource("*", "*", container)
        can = {
            "create": session.authorize("iam:CreatePolicy", any_policy).allowed,
            "attach": session.authorize("iam:AttachPolicy", any_attachment).allowed,
            "detach": session.authorize("iam:DetachPolicy", any_attachment).allowed,
            "widen": bool(access_id)
            and session.authorize(
                "iam:UpdatePolicy", policy_resource(access_id, container)
            ).allowed,
        }
        chain = self._chain(access_id)
        grantable = session.grantable(container)
        managed_ids = set(known.values())
        others = [
            p
            for p in self._policies_at(session, container)
            if not p.managed and p.id not in managed_ids
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
                    session,
                    key,
                    resource,
                    container,
                    access_id=access_id,
                    members_id=members_id,
                    policy_id=known.get(key),
                    can=can,
                    offered_here=offered(chain, resource, container),
                    held=holds(grantable, resource, container),
                    also=also,
                )
            )
        access = chain[0] if chain else None
        return {
            "workspace_id": workspace_id,
            "scope": container,
            "access_policy": _ref(access) if access is not None else None,
            "members_group": self._principal(members_id) if members_id else None,
            "can": can,
            "features": rows,
        }

    def _row(
        self,
        session: IIAMService,
        key: str,
        resource: str,
        container: str,
        *,
        access_id: str | None,
        members_id: str | None,
        policy_id: str | None,
        can: dict[str, bool],
        offered_here: bool,
        held: bool,
        also: list[dict[str, Any]],
    ) -> dict[str, Any]:
        policy = self._gateway.policy(policy_id) if policy_id else None
        hand_edited = policy is not None and not as_written(policy, key, container, access_id)
        attachments = session.list_attachments(policy_id=policy.id) if policy is not None else []
        holders = [a.principal_id for a in attachments if a.scope == container]
        if members_id and members_id in holders:
            choice = "everyone"
        elif attachments:
            choice = "only"
        else:
            choice = "nobody"
        label = feature_label(key)
        reason: str | None = None
        if not access_id or not members_id:
            reason = "This workspace has no access policy or members group yet."
        elif hand_edited:
            reason = f"{policy_name(key)} was changed on its policy page: change it there."
        elif not held:
            reason = f"You do not hold {label} here, so you cannot give it or take it back."
        elif not (can["attach"] and can["detach"] and (policy is not None or can["create"])):
            reason = "IAM does not let you create, attach and detach policies here."
        return {
            "key": key,
            "label": label,
            "choice": choice,
            "principals": [self._principal(p) for p in holders] if choice == "only" else [],
            "policy": _ref(policy) if policy is not None else None,
            "hand_edited": hand_edited,
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
            try:
                await self._apply(user, workspace_id, container, record, row, change)
            except (PermissionDeniedError, IAMNotFoundError, IAMConflictError, ValueError) as exc:
                errors[change.feature] = str(exc)
        after = await self.read(user, workspace_id)
        return {**after, "errors": errors}

    @staticmethod
    def _refusal(row: dict[str, Any], change: FeatureChange, state: dict[str, Any]) -> str | None:
        if not row["editable"]:
            return row["reason"]
        if change.choice != "nobody" and not row["offered"]:
            access = (state.get("access_policy") or {}).get(
                "name"
            ) or "the workspace's access policy"
            return f"{row['label']} is not offered in this workspace: widen {access} first."
        return None

    async def _apply(
        self,
        user: Any,
        workspace_id: str,
        container: str,
        record: Any,
        row: dict[str, Any],
        change: FeatureChange,
    ) -> None:
        key = change.feature
        policy_id = row["policy"]["id"] if row["policy"] else None
        if policy_id is None and change.choice == "nobody":
            return
        if policy_id is None:
            created = await self._change(
                user,
                "feature-access.create",
                f"{workspace_id}/{key}",
                lambda s: s.create_policy(
                    policy_name(key),
                    feature_document(key),
                    description=policy_description(key),
                    scope=container,
                    parent=record.access_policy_id,
                ),
            )
            policy_id = created.id
            try:
                await self._store.put(workspace_id, key, policy_id)
            except Exception:
                _log.exception(f"{policy_id} ({key} in {workspace_id}) could not be recorded")
                await run_in_threadpool(self._gateway.bind(user).delete_policy, policy_id)
                raise
        if change.choice == "everyone":
            wanted = {record.members_group_id}
        elif change.choice == "only":
            wanted = set(change.principals)
        else:
            wanted = set()
        detail = ",".join(sorted(wanted)) if change.choice == "only" else ""
        found = policy_id

        def attach_only(session: IIAMService) -> None:
            current = session.list_attachments(policy_id=found)
            have = {a.principal_id for a in current if a.scope == container}
            for principal_id in sorted(wanted - have):
                session.attach_policy(found, principal_id, container)
            for a in current:
                if a.scope != container or a.principal_id not in wanted:
                    session.detach_policy(found, a.principal_id, a.scope)

        await self._change(
            user, f"feature-access.{change.choice}", found, attach_only, detail=detail
        )

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
        """``{policy id: feature}``: those General manages, marked on Access › Policies."""
        return await self._store.managed_among(policy_ids)


__all__ = ["FeatureAccessService", "check_changes", "feature_document", "policy_name"]
