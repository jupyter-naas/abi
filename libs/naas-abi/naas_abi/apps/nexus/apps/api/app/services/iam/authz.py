"""Every Nexus authorization decision, asked of IAM.

A route asks ``authz.require("UpdateWorkspace", user=current_user,
workspace=workspace_id)``: the action of the ``nexus`` catalog, on the resource
it names, for the signed-in user. The decision is IAM's: ``api`` acting on
behalf of that user, so both must be allowed. There is no role check outside
IAM and no scope list.

* **Identity** is the call's own ``CallContext`` when it already names this
  user (the middleware set it from the verified session), else ``api`` on
  behalf of ``user`` (a route whose ``current_user`` dependency verified it).
  Never a request field.
* **Features.** An action of a flagged section needs ``nexus:UseFeature`` on
  the feature first (``catalog.FEATURE_OF``, or ``feature=`` where the feature
  depends on the resource, as for slides, documents and sheets).
* **Denials.** A caller who may not perform the action but sees the workspace
  (or organization) gets 403. One who sees nothing of it gets 403 "no access".
  Another user's personal resource (a conversation) is not found: 404.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import (
    FEATURE_OF,
    TYPE_OF,
    TYPES_BY_NAME,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    NO_ORG,
    RESERVED_WORKSPACE_IDS,
    nexus_resource,
)
from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    CallContext,
    Principal,
    current_call_context,
    service_account,
    use_call_context,
)
from starlette.concurrency import run_in_threadpool

NEXUS_IDENTITY = "api"
_T = TypeVar("_T")
# How long a workspace's org is remembered by this process: a change made here
# forgets it at once (``forget_workspace``); one made elsewhere is seen in this time.
_ORG_CACHE_SECONDS = 30.0


class AuthzDenied(HTTPException):
    """A refusal, as the HTTP response it is."""


@dataclass(frozen=True)
class Decision:
    """IAM's decision, with ``feature_disabled`` for a flag that is off."""

    allowed: bool
    visible: bool
    reason: str


class Authz:
    def __init__(self) -> None:
        self._orgs: dict[str, tuple[str, float]] = {}

    # -- identity ------------------------------------------------------------

    @staticmethod
    def user_id(user: Any) -> str | None:
        if user is None:
            return None
        return user if isinstance(user, str) else getattr(user, "id", None)

    def context(self, user: Any = None) -> CallContext:
        """The call to decide for: the ambient one when it names ``user``."""
        ambient = current_call_context()
        user_id = self.user_id(user)
        named = ambient.on_behalf_of
        if user_id is None or (named is not None and named.id == user_id):
            return ambient
        return replace(
            ANONYMOUS,
            principal=service_account(NEXUS_IDENTITY),
            on_behalf_of=Principal(id=user_id, kind="user"),
            workspace_id=ambient.workspace_id,
            triggered_via=ambient.triggered_via,
        )

    # -- names ---------------------------------------------------------------

    async def org_of(self, workspace: str) -> str | None:
        """The org a workspace sits in (``_none`` for none), as IAM registered it;
        None for an unknown workspace and for ids that name none (``-``, ``*``)."""
        if workspace in RESERVED_WORKSPACE_IDS:
            return None
        found = self._orgs.get(workspace)
        now = time.monotonic()
        if found is not None and found[1] > now:
            return found[0]
        org = await run_in_threadpool(runtime.iam().workspace_org, workspace)
        if org is not None:
            self._orgs[workspace] = (org, now + _ORG_CACHE_SECONDS)
        return org

    def forget_workspace(self, workspace: str) -> None:
        self._orgs.pop(workspace, None)

    async def name(
        self,
        action_or_type: str,
        *,
        workspace: str | None = None,
        org: str | None = None,
        id: str | Sequence[str] = (),
    ) -> str | None:
        """The resource name of an action's (or a type's) resource; None when the
        workspace is unknown to IAM."""
        type_name = TYPE_OF.get(action_or_type, action_or_type)
        if workspace in RESERVED_WORKSPACE_IDS and workspace is not None:
            return None
        if workspace is not None and org is None:
            org = await self.org_of(workspace)
            if org is None:
                return None
        return nexus_resource(type_name, org=org, workspace=workspace, id=id)

    # -- decisions -----------------------------------------------------------

    async def _decide(self, ctx: CallContext, action: str, resource: str) -> Decision:
        def run() -> Decision:
            with use_call_context(ctx):
                found = runtime.iam().authorize(action, resource)
            return Decision(found.allowed, found.visible, found.reason)

        return await run_in_threadpool(run)

    async def decide(
        self,
        action: str,
        *,
        user: Any = None,
        workspace: str | None = None,
        org: str | None = None,
        id: str | Sequence[str] = (),
        feature: str | None = None,
    ) -> Decision:
        """The decision for ``action`` on its resource; the feature's first."""
        ctx = self.context(user)
        resource = await self.name(action, workspace=workspace, org=org, id=id)
        if resource is None:
            return Decision(False, False, "implicit_deny")
        flag = feature if feature is not None else FEATURE_OF.get(action)
        if flag is not None and workspace is not None:
            feature_resource = await self.name("feature", workspace=workspace, org=org, id=flag)
            assert feature_resource is not None
            used = await self._decide(ctx, "nexus:UseFeature", feature_resource)
            if not used.allowed:
                return Decision(False, False, "feature_disabled")
        return await self._decide(ctx, f"nexus:{action}", resource)

    async def allowed_in_any(
        self,
        action: str,
        *,
        user: Any,
        workspaces: Sequence[tuple[str, str]],
        id: str | Sequence[str] = (),
        feature: str | None = None,
    ) -> bool:
        """Whether any of ``workspaces`` (``(org, workspace)`` pairs) lets the user
        perform ``action``: two ``filter`` calls over all of them (the feature
        switch, then the action), in one worker thread."""
        ctx = self.context(user)
        flag = feature if feature is not None else FEATURE_OF.get(action)
        type_name = TYPE_OF[action]
        pairs = list(workspaces)
        if not pairs:
            return False

        def run() -> bool:
            iam = runtime.iam()
            candidates = pairs
            with use_call_context(ctx):
                if flag is not None:
                    switches = {
                        pair: nexus_resource("feature", org=pair[0], workspace=pair[1], id=flag)
                        for pair in candidates
                    }
                    usable = set(iam.filter("nexus:UseFeature", list(switches.values())).allowed)
                    candidates = [pair for pair in candidates if switches[pair] in usable]
                    if not candidates:
                        return False
                resources = [
                    nexus_resource(type_name, org=org, workspace=workspace, id=id)
                    for org, workspace in candidates
                ]
                return bool(iam.filter(f"nexus:{action}", resources).allowed)

        return await run_in_threadpool(run)

    async def allowed(self, action: str, **target: Any) -> bool:
        return (await self.decide(action, **target)).allowed

    async def require(
        self,
        action: str,
        *,
        user: Any = None,
        workspace: str | None = None,
        org: str | None = None,
        id: str | Sequence[str] = (),
        feature: str | None = None,
        denied: str | None = None,
    ) -> None:
        """Raise ``AuthzDenied`` unless the user may perform ``action``."""
        decision = await self.decide(
            action, user=user, workspace=workspace, org=org, id=id, feature=feature
        )
        if decision.allowed:
            return
        raise await self._refusal(
            action, decision, user=user, workspace=workspace, org=org, denied=denied
        )

    async def _refusal(
        self,
        action: str,
        decision: Decision,
        *,
        user: Any,
        workspace: str | None,
        org: str | None,
        denied: str | None,
    ) -> AuthzDenied:
        if decision.reason == "feature_disabled":
            # Who sees nothing of the workspace is told so, not about its features.
            where = await self.name("workspace", workspace=workspace, org=org)
            ctx = self.context(user)
            if where is None or not (await self._decide(ctx, "nexus:GetWorkspace", where)).allowed:
                return AuthzDenied(403, detail="You do not have access to this workspace")
            return AuthzDenied(403, detail="This feature is not available to you in this workspace")
        if decision.visible:
            return AuthzDenied(403, detail=denied or "You do not have permission to do this")
        # The caller sees nothing of the resource. Where it should be is no
        # secret for the sections everyone knows (members, domains, servers):
        # 403. Another user's personal resource is invisible (404), and a caller
        # who sees nothing of the workspace or organization is told it has no
        # access there at all.
        ctx = self.context(user)
        personal = TYPES_BY_NAME[TYPE_OF[action]].personal if action in TYPE_OF else False
        if workspace is not None:
            where = await self.name("workspace", workspace=workspace, org=org)
            if where is not None and (await self._decide(ctx, "nexus:GetWorkspace", where)).allowed:
                if personal:
                    return AuthzDenied(404, detail="Not found")
                return AuthzDenied(403, detail=denied or "You do not have permission to do this")
            return AuthzDenied(403, detail="You do not have access to this workspace")
        if org is not None:
            where = nexus_resource("organization", org=org)
            if (await self._decide(ctx, "nexus:GetOrganization", where)).allowed:
                return AuthzDenied(403, detail=denied or "You do not have permission to do this")
            return AuthzDenied(403, detail="You do not have access to this organization")
        return AuthzDenied(403, detail=denied or "You do not have permission to do this")

    async def filter(
        self,
        action: str,
        items: Iterable[_T],
        *,
        user: Any = None,
        resource_of: Callable[[_T], str],
    ) -> list[_T]:
        """The items the user may perform ``action`` on, in order.

        ``resource_of`` names each item (``authz.name`` is async, so build names
        with ``nexus_resource`` where the org is known).
        """
        found = list(items)
        ctx = self.context(user)
        names = [resource_of(item) for item in found]

        def run() -> set[str]:
            with use_call_context(ctx):
                return set(runtime.iam().filter(f"nexus:{action}", names).allowed)

        allowed = await run_in_threadpool(run)
        return [item for item, name in zip(found, names, strict=True) if name in allowed]


AUTHZ = Authz()
require = AUTHZ.require
allowed = AUTHZ.allowed
decide = AUTHZ.decide
filter_allowed = AUTHZ.filter
name = AUTHZ.name

__all__ = [
    "AUTHZ",
    "NO_ORG",
    "TYPES_BY_NAME",
    "Authz",
    "AuthzDenied",
    "allowed",
    "decide",
    "filter_allowed",
    "name",
    "require",
]
