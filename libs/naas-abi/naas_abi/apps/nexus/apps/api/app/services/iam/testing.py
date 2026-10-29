"""A real IAM for Nexus tests: kernel and Nexus catalogs on the memory store.

``NexusIam`` installs itself as Nexus's IAM (``runtime.configure``), so a test
sets up memberships as the routes do (role attachments) and asserts what the
routes then decide. Nothing here fakes a decision.

No role brings a feature: a policy does. By default ``grant`` also attaches the
features ``flags`` gave that role (``role_features``), as the policy "Features of
<role>" an invitation carries; ``features_with_roles=False`` is the bare world,
where a member uses no feature until a test grants one. While installed, the
deployment's ``enabled_features`` are ``flags``'s.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam import (
    container_names,
    legacy_names,
    role_features,
    runtime,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import shared_repo_grants
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import NEXUS_CATALOG
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, Memberships
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    ORGANIZATION,
    PLATFORM,
    SERVICE,
    WORKSPACE,
    is_org_container,
    org_below,
    org_of,
)
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import Policy, PrincipalRecord, new_id
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER, IAMService
from naas_abi_core.services.iam.kernel_catalogs import register_kernel_catalogs
from naas_abi_core.services.iam.policy import PolicyDocument, Statement


class NexusIam:
    def __init__(
        self,
        flags: FeatureFlagsConfig | None = None,
        *,
        org_overlays: Mapping[str, Mapping[str, list[str]]] | None = None,
        features_with_roles: bool = True,
        store: Any | None = None,
    ) -> None:
        self.flags = flags or FeatureFlagsConfig()
        self.org_overlays = dict(org_overlays or {})
        self.features_with_roles = features_with_roles
        self._feature_policies: dict[tuple[str, ...], str] = {}
        # ``store``: an IAM store of another adapter (SQLite, PostgreSQL); memory by default.
        self.iam = IAMService(store if store is not None else IAMStoreMemory())
        self.iam.bootstrap()
        register_kernel_catalogs(self.iam)
        with as_service_account("engine"):
            self.iam.register_catalog(NEXUS_CATALOG)
            self.iam.set_platform_grants(shared_repo_grants("abi/monorepo"))
        self.authz = authz_module.AUTHZ

    # -- the world: orgs, workspaces and who holds what -------------------------

    def workspace(self, org: str | None, workspace: str) -> str:
        """Register a workspace (and its org) with IAM as containers, as Nexus does;
        returns the workspace's container name (at the platform with no org)."""
        parent = self.org(org) if org else PLATFORM
        with as_service_account("api"):
            return self.iam.register_container(SERVICE, WORKSPACE, workspace, parent=parent).name

    def org(self, org: str) -> str:
        """Register an organization with IAM; returns its container name."""
        with as_service_account("api"):
            return self.iam.register_container(SERVICE, ORGANIZATION, org).name

    def grant(self, user_id: str, role: str, scope: str) -> None:
        """Attach ``builtin.<role>`` at ``scope`` for a Nexus user id."""
        with as_service_account("api"):
            principal = self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
            self.iam.attach_policy(f"builtin.{role}", principal.id, scope)
            # As MEMBERSHIPS does: an org owner or admin holds the role below the org.
            Memberships.mirror_org_wide(self.iam, principal.id, scope, role)
        if self.features_with_roles:
            self._give_role_features(principal.id, role, scope)

    def _give_role_features(self, principal_id: str, role: str, scope: str) -> None:
        """Attach what ``role`` brought where it is held: at a workspace, and below
        the org (each of its workspaces) for an org owner or admin."""
        org = org_of(scope)
        if is_org_container(scope):
            if role not in ("owner", "admin") or org is None:
                return
            scope = org_below(org)
        features = self.role_features(org).get(role, ())
        if features:
            self.give_features(principal_id, features, scope)

    def role_features(self, org: str | None) -> dict[str, tuple[str, ...]]:
        """``{role: features}`` ``flags`` gave each role in ``org``, within
        ``enabled_features``: what this world's "Features of <role>" hold."""
        from naas_abi.apps.nexus.apps.api.app.core.feature_flags import enabled_feature_catalog

        resolved = role_features.resolve_role_baseline(
            self.flags,
            organization_id=org,
            organization_override=self.org_overlays.get(org) if org else None,
        )
        return {
            role: tuple(
                k for k in enabled_feature_catalog(self.flags) if k in set(resolved.get(role) or ())
            )
            for role in role_features.ROLE_NAMES
        }

    def give_features(self, principal_id: str, features: Sequence[str], scope: str) -> str:
        """Attach to a principal, at ``scope``, a policy allowing ``features``
        (one platform policy per set of features). Returns its id."""
        key = tuple(sorted(set(features)))
        with as_service_account("engine"):
            policy_id = self._feature_policies.get(key)
            if policy_id is None:
                policy_id = self.iam.create_policy(
                    f"Features {', '.join(key)}", features_document(key)
                ).id
                self._feature_policies[key] = policy_id
            self.iam.attach_policy(policy_id, principal_id, scope)
        return policy_id

    def allow(
        self, user_id: str, actions: Sequence[str], resources: Sequence[str], scope: str
    ) -> str:
        """Attach to a Nexus user, at ``scope``, a policy allowing ``actions`` on
        ``resources`` (``${scope}/`` patterns): a grant an admin makes, one
        module scope at a time. Returns the policy id."""
        with as_service_account("engine"):
            principal = self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
            policy = self.iam.create_policy(
                f"allow-{user_id}-{uuid.uuid4().hex[:8]}",
                {
                    "version": "2026-10-13",
                    "statements": [
                        {
                            "effect": "Allow",
                            "actions": list(actions),
                            "resources": list(resources),
                        }
                    ],
                },
            )
            self.iam.attach_policy(policy.id, principal.id, scope)
        return policy.id

    def allow_scope(self, user_id: str, scope: Any, workspace_scope: str) -> str:
        """Grant a user one module scope (``authz.ModuleScope``) at a workspace."""
        resource = scope.resource(PLATFORM).removeprefix(PLATFORM)
        return self.allow(user_id, [scope.action()], [f"${{scope}}/{resource}"], workspace_scope)

    def platform_admin(self, user_id: str) -> None:
        with as_service_account("api"):
            principal = self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
            self.iam.attach_policy(roles.PLATFORM_ADMIN, principal.id)

    def user(self, user_id: str) -> None:
        self.principal(user_id)

    def principal(self, user_id: str) -> str:
        """The IAM principal of a Nexus user id, made on first sight."""
        with as_service_account("api"):
            return self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus").id

    @staticmethod
    def context(user_id: str | None) -> CallContext:
        """Nexus's own context for a request: ``api`` on behalf of the user."""
        return CallContext(
            principal=service_account("api"),
            on_behalf_of=Principal(id=user_id, kind="user") if user_id else None,
        )

    # -- installation -------------------------------------------------------------

    @contextmanager
    def installed(self) -> Iterator[NexusIam]:
        """Make this Nexus's IAM, and ``flags`` the deployment's features; the
        container cache of the authorizer starts empty."""
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

        previous = runtime.configure(lambda: self.iam)
        live = live_settings()
        previous_flags = live.feature_flags
        live.feature_flags = self.flags
        self.authz.forget_workspaces()
        try:
            with use_call_context(self.context(None)):
                yield self
        finally:
            self.authz.forget_workspaces()
            live.feature_flags = previous_flags
            runtime.configure(previous)


class LegacyNexusIam(NexusIam):
    """The IAM of an install before container paths, for the start-up moves that
    predate them (``feature_overrides``, ``role_features``, ``policy_tree``).

    As that install stored it: roles attached at ``abi:<org>:<ws>`` and
    ``abi:<org>:-``, an org owner's or admin's mirrored org-wide at
    ``abi:<org>:*``, the built-in roles as the engine of then generated them (the
    same statements, on names of that grammar), and no container registered.
    Everything is written as ``api`` or the engine for no user: the only accounts
    core takes that grammar from. ``rewrite`` is the move of the names
    (``container_names``); from then on the world is ``NexusIam``'s (a workspace
    made or a role given is in the grammar of today).
    """

    def __init__(self, flags: FeatureFlagsConfig | None = None, *, store: Any | None = None):
        super().__init__(flags, features_with_roles=False, store=store)
        self.orgs: list[str] = []
        self.workspaces: dict[str, str | None] = {}
        self.rewritten = False
        store_old_roles(self.iam)

    def workspace(self, org: str | None, workspace: str) -> str:
        """A workspace (and its org) Nexus knows; returns its old scope."""
        if self.rewritten:
            return super().workspace(org, workspace)
        if org is not None:
            self.org(org)
        self.workspaces[workspace] = org
        return legacy_names.workspace_scope(org, workspace)

    def org(self, org: str) -> str:
        if self.rewritten:
            return super().org(org)
        if org not in self.orgs:
            self.orgs.append(org)
        return legacy_names.org_scope(org)

    def grant(self, user_id: str, role: str, scope: str) -> None:
        """Attach ``builtin.<role>`` at an old ``scope``; an org owner or admin
        also org-wide, as Nexus mirrored it then."""
        if self.rewritten:
            return super().grant(user_id, role, scope)
        with as_service_account("api"):
            principal = self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
            self.iam.attach_policy(f"builtin.{role}", principal.id, scope)
            if scope.endswith(":-") and role in ("owner", "admin"):
                self.iam.attach_policy(f"builtin.{role}", principal.id, f"{scope[:-1]}*")

    def group(self, name: str, scope: str | None = None) -> str:
        """A group owned by an old ``scope`` (the platform without), stored as the
        IAM of then made it: IAM of today makes none there. Returns its id."""
        owner = scope or "abi:-:-"
        record = PrincipalRecord(id=new_id("grp"), kind="group", name=name, owner_scope=owner)
        self.iam.store.create_principal(record)
        self.iam.invalidate()
        return record.id

    def add_member(self, group_id: str, principal_id: str) -> None:
        self.iam.store.add_group_member(group_id, principal_id)
        self.iam.invalidate()

    def rewrite(self) -> container_names.Report:
        """The move of the names: containers registered, every name a path."""
        report = container_names.rewrite(self.iam, self.orgs, self.workspaces)
        self.rewritten = True
        self.iam.invalidate()
        return report


def store_old_roles(iam: IAMService) -> None:
    """The built-in roles as the engine before container paths stored them:
    ``${scope}/<rest>`` was ``${scope}:<rest>``, and a container itself its
    singleton (``${scope}:nexus:workspace/-``, ``${scope}:nexus:organization/-``).
    The engine of today regenerates them at its start (``bootstrap``)."""
    for role in roles.ROLES:
        policy = iam.store.get_policy(role)
        statements = tuple(
            Statement(
                s.effect,
                s.actions,
                tuple(
                    found
                    for resource in s.resources
                    for found in (
                        (
                            f"${{scope}}:{SERVICE}:{WORKSPACE}/-",
                            f"${{scope}}:{SERVICE}:{ORGANIZATION}/-",
                        )
                        if resource == "${scope}"
                        else (resource.replace("${scope}/", "${scope}:", 1),)
                    )
                ),
                sid=s.sid,
            )
            for s in policy.document.statements
        )
        iam.store.put_managed_policy(
            Policy(
                id=policy.id,
                name=policy.name,
                description=policy.description,
                document=PolicyDocument(statements=statements),
                managed=True,
            )
        )
    iam.invalidate()


def features_document(features: Sequence[str]) -> PolicyDocument:
    """Allow ``UseFeature`` on ``features`` where the policy is attached: what a
    "Features of <role>" policy grants."""
    return PolicyDocument(
        statements=(
            Statement(
                "Allow",
                ("nexus:UseFeature",),
                tuple(f"${{scope}}/nexus:feature/{key}" for key in features),
                sid="UseFeatures",
            ),
        )
    )


def memberships() -> Any:
    return MEMBERSHIPS
