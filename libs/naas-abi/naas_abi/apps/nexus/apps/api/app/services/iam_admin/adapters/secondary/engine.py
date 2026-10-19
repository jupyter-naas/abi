"""The engine's IAM, as the signed-in user.

Nexus runs inside the engine and calls its IAM service in process. A call made for
the admin pages carries the user as its actor, from the verified session the
request middleware recorded (their groups from the IdP included): IAM then
decides by that user's own policies, which is the point of the pages. Nothing in
the request names who the caller is.

The profile of a principal and the name of a policy are read as ``api``, for ids
the caller already holds (the ones in a list they may read).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import (
    IamGateway,
    IamUnavailableError,
)
from naas_abi_core.engine.call_context import CallContext, as_service_account, use_call_context
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    IIAMService,
    PermissionDeniedError,
    Policy,
    PrincipalRecord,
)

_PAGE = 200


class _BoundIam:
    """IAM, every call of it made as ``context``."""

    def __init__(self, iam: Any, context: CallContext) -> None:
        self._iam = iam
        self._context = context

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._iam, name)
        if not callable(target):
            return target

        def call(*args: Any, **kwargs: Any) -> Any:
            with use_call_context(self._context):
                return target(*args, **kwargs)

        return call


class EngineIamGateway(IamGateway):
    def _iam(self) -> Any:
        try:
            return runtime.iam()
        except runtime.IAMUnavailableError as exc:
            raise IamUnavailableError(str(exc)) from exc

    def bind(self, user: Any) -> IIAMService:
        context = AUTHZ.context(user)
        caller = context.on_behalf_of
        if caller is None:
            # Nobody is signed in: IAM decides for an anonymous caller, who holds nothing.
            raise PermissionDeniedError(message="Sign in to manage permissions")
        acting = replace(context, principal=caller, on_behalf_of=None)
        return cast(IIAMService, _BoundIam(self._iam(), acting))

    def catalogs(self) -> CatalogRegistry:
        registry = getattr(self._iam(), "catalogs", None)
        if not isinstance(registry, CatalogRegistry):
            raise IamUnavailableError("IAM does not publish its action catalogs here")
        return registry

    def principal(self, principal_id: str) -> PrincipalRecord | None:
        iam = self._iam()
        with as_service_account("api"):
            try:
                return iam.get_principal(principal_id)
            except (IAMNotFoundError, PermissionDeniedError):
                return None

    def policy(self, policy_id: str) -> Policy | None:
        iam = self._iam()
        with as_service_account("api"):
            try:
                return iam.get_policy(policy_id)
            except (IAMNotFoundError, PermissionDeniedError):
                return None

    def policies(self) -> list[Policy]:
        iam = self._iam()
        found: list[Policy] = []
        after: str | None = None
        with as_service_account("api"):
            while True:
                page = iam.list_policies(limit=_PAGE, after=after)
                found += page.items
                after = page.next_after
                if after is None:
                    return found
