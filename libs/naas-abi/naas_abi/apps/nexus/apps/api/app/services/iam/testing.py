"""A real IAM for Nexus tests: kernel and Nexus catalogs on the memory store.

``NexusIam`` installs itself as Nexus's IAM (``runtime.configure``), so a test
sets up memberships as the routes do (role attachments) and asserts what the
routes then decide. Nothing here fakes a decision.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import (
    feature_plan,
    shared_repo_grants,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import NEXUS_CATALOG
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
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


class NexusIam:
    def __init__(
        self,
        flags: FeatureFlagsConfig | None = None,
        *,
        org_overlays: Mapping[str, Mapping[str, list[str]]] | None = None,
        workspaces: Sequence[tuple[str, str | None, str | None]] = (),
    ) -> None:
        self.iam = IAMService(IAMStoreMemory())
        self.iam.bootstrap()
        register_kernel_catalogs(self.iam)
        with as_service_account("engine"):
            self.iam.register_catalog(NEXUS_CATALOG)
            self.iam.put_feature_policies(
                feature_plan(
                    flags or FeatureFlagsConfig(),
                    org_overlays=org_overlays or {},
                    workspaces=workspaces,
                )
            )
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

    def platform_admin(self, user_id: str) -> None:
        with as_service_account("api"):
            principal = self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
            self.iam.attach_policy(roles.PLATFORM_ADMIN, principal.id)

    def user(self, user_id: str) -> None:
        with as_service_account("api"):
            self.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")

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
        """Make this Nexus's IAM; the org cache of the authorizer starts empty."""
        previous = runtime.configure(lambda: self.iam)
        self.authz._orgs.clear()
        try:
            with use_call_context(self.context(None)):
                yield self
        finally:
            self.authz._orgs.clear()
            runtime.configure(previous)


def memberships() -> Any:
    return MEMBERSHIPS
