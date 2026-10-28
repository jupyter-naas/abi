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
from naas_abi.apps.nexus.apps.api.app.services.iam import role_features, runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import shared_repo_grants
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import NEXUS_CATALOG
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, Memberships
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    NO_ORG,
    org_scope,
    workspace_scope,
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
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER, IAMService
from naas_abi_core.services.iam.kernel_catalogs import register_kernel_catalogs
from naas_abi_core.services.iam.names import scope_fields


class NexusIam:
    def __init__(
        self,
        flags: FeatureFlagsConfig | None = None,
        *,
        org_overlays: Mapping[str, Mapping[str, list[str]]] | None = None,
        features_with_roles: bool = True,
    ) -> None:
        self.flags = flags or FeatureFlagsConfig()
        self.org_overlays = dict(org_overlays or {})
        self.features_with_roles = features_with_roles
        self._feature_policies: dict[tuple[str, ...], str] = {}
        self.iam = IAMService(IAMStoreMemory())
        self.iam.bootstrap()
        register_kernel_catalogs(self.iam)
        with as_service_account("engine"):
            self.iam.register_catalog(NEXUS_CATALOG)
            self.iam.set_platform_grants(shared_repo_grants("abi/monorepo"))
        self.authz = authz_module.AUTHZ

    # -- the world: orgs, workspaces and who holds what -------------------------

    def workspace(self, org: str | None, workspace: str) -> str:
        """Register a workspace (and its org) with IAM; returns its scope."""
        with as_service_account("api"):
            self.iam.put_scope(org or NO_ORG)
            self.iam.put_scope(org or NO_ORG, workspace)
        return workspace_scope(org, workspace)

    def org(self, org: str) -> str:
        with as_service_account("api"):
            self.iam.put_scope(org)
        return org_scope(org)

    def grant(self, user_id: str, role: str, scope: str) -> None:
        """Attach ``builtin.<role>`` at ``scope`` for a Nexus user id."""
        with as_service_account("api"):
            principal = self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
            self.iam.attach_policy(f"builtin.{role}", principal.id, scope)
            # As MEMBERSHIPS does: an org owner or admin reaches every workspace of the org.
            Memberships.mirror_org_wide(self.iam, principal.id, scope, role)
        if self.features_with_roles:
            self._give_role_features(principal.id, role, scope)

    def _give_role_features(self, principal_id: str, role: str, scope: str) -> None:
        """Attach what ``role`` brought where it is held: at a workspace, and in
        every workspace of the org for an org owner or admin (org-wide)."""
        org, workspace = scope_fields(scope)
        if workspace == "-":
            if role not in ("owner", "admin"):
                return
            scope = f"abi:{org}:*"
        features = self.role_features(None if org == NO_ORG else org).get(role, ())
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
                    f"Features {', '.join(key)}", role_features.policy_document(key)
                ).id
                self._feature_policies[key] = policy_id
            self.iam.attach_policy(policy_id, principal_id, scope)
        return policy_id

    def allow(
        self, user_id: str, actions: Sequence[str], resources: Sequence[str], scope: str
    ) -> str:
        """Attach to a Nexus user, at ``scope``, a policy allowing ``actions`` on
        ``resources`` (``${scope}:`` patterns): a grant an admin makes, one
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
        resource = scope.resource("o", "w").removeprefix("abi:o:w:")
        return self.allow(user_id, [scope.action()], [f"${{scope}}:{resource}"], workspace_scope)

    def put_set(
        self,
        org: str,
        workspace: str = "-",
        *,
        modules: Sequence[str] | None = None,
        features: Sequence[str] | None = None,
    ) -> None:
        """Record the set of an org (or of a workspace in it), as the platform's."""
        with as_service_account("engine"):
            self.iam.put_set(org, workspace, modules=modules, features=features)

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
        org cache of the authorizer starts empty."""
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

        previous = runtime.configure(lambda: self.iam)
        live = live_settings()
        previous_flags = live.feature_flags
        live.feature_flags = self.flags
        self.authz._orgs.clear()
        try:
            with use_call_context(self.context(None)):
                yield self
        finally:
            self.authz._orgs.clear()
            live.feature_flags = previous_flags
            runtime.configure(previous)


def memberships() -> Any:
    return MEMBERSHIPS
