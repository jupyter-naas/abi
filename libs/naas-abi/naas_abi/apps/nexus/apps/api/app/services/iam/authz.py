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
* **Module scopes.** What a module exposes (an agent, app, workflow or
  pipeline: ``ModuleScope``) is decided with the ``module`` catalog, in the
  workspace where it is used (``require_scope``, ``filter_scopes``): one
  source of truth for module resources, whoever hosts them. Agents a workspace
  builds itself stay ``nexus:UseAgent``.
* **Hidden in the workspace.** One its admins turned off there
  (``services/visibility``) is refused to everyone after IAM allows using it
  (its use action; reading one's own runs of it is not a use: reason
  ``hidden``), and left out of ``filter_scopes``; the settings pages that turn
  it back on pass ``include_hidden``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable, Sequence
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
from naas_abi_core.services.iam import module_scopes
from starlette.concurrency import run_in_threadpool

NEXUS_IDENTITY = "api"
_T = TypeVar("_T")
# How long a workspace's org is remembered by this process: a change made here
# forgets it at once (``forget_workspace``); one made elsewhere is seen in this time.
_ORG_CACHE_SECONDS = 30.0


class AuthzDenied(HTTPException):
    """A refusal, as the HTTP response it is."""


@dataclass(frozen=True)
class ModuleScope:
    """An agent, app, workflow or pipeline of a module (core ``module_scopes``):
    ``module`` is the module's stable identifier (an engine module's configured
    path, a remote module's id), ``name`` the item's own."""

    type: str
    module: str
    name: str

    def action(self, action: str | None = None) -> str:
        """The qualified action: the type's use action by default."""
        return f"{module_scopes.SERVICE}:{action or module_scopes.USE_ACTION[self.type]}"

    def is_use(self, action: str | None = None) -> bool:
        """Whether ``action`` uses it (its use action), which turning it off in a
        workspace refuses; reading one's own runs of it is not a use."""
        return self.action(action) == self.action()

    def resource(self, org: str, workspace: str) -> str:
        return module_scopes.scope_resource(
            self.type, self.module, self.name, org=org, workspace=workspace
        )


@dataclass(frozen=True)
class Decision:
    """IAM's decision, with ``feature_disabled`` for a flag that is off."""

    allowed: bool
    visible: bool
    reason: str


async def _hidden(workspace: str, scopes: Sequence[ModuleScope]) -> set[ModuleScope]:
    """The ``scopes`` the workspace turned off (``services/visibility``)."""
    from naas_abi.apps.nexus.apps.api.app.services.visibility import runtime as visibility

    found = visibility.current()
    if found is None or not scopes:
        return set()
    return await found.hidden(workspace, list(scopes))


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

    async def allowed_ids(
        self, action: str, *, user: Any, workspace: str, ids: Iterable[str]
    ) -> set[str]:
        """The ``ids`` of the workspace's ``action`` resources the user may act on:
        the action's feature once, then one ``filter`` (a listing asks each row's
        own right without a call per row)."""
        wanted = list(dict.fromkeys(ids))
        org = await self.org_of(workspace) if wanted else None
        if org is None:
            return set()
        ctx = self.context(user)
        flag = FEATURE_OF.get(action)
        if flag is not None:
            switch = nexus_resource("feature", org=org, workspace=workspace, id=flag)
            if not (await self._decide(ctx, "nexus:UseFeature", switch)).allowed:
                return set()
        names = {
            nexus_resource(TYPE_OF[action], org=org, workspace=workspace, id=one): one
            for one in wanted
        }

        def run() -> set[str]:
            with use_call_context(ctx):
                found = runtime.iam().filter(f"nexus:{action}", list(names)).allowed
            return {names[name] for name in found}

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

    # -- module scopes ---------------------------------------------------------

    async def decide_scope(
        self,
        scope: ModuleScope,
        *,
        user: Any = None,
        workspace: str,
        action: str | None = None,
        feature: str | None = None,
        include_hidden: bool = False,
    ) -> Decision:
        """The decision on a module scope in ``workspace`` (its use action by
        default); ``feature`` is a Nexus section the use also needs. One the
        workspace turned off is refused (``hidden``) unless ``include_hidden``."""
        org = await self.org_of(workspace)
        if org is None:
            return Decision(False, False, "implicit_deny")
        ctx = self.context(user)
        if feature is not None:
            switch = nexus_resource("feature", org=org, workspace=workspace, id=feature)
            if not (await self._decide(ctx, "nexus:UseFeature", switch)).allowed:
                return Decision(False, False, "feature_disabled")
        decision = await self._decide(ctx, scope.action(action), scope.resource(org, workspace))
        if (
            decision.allowed
            and not include_hidden
            and scope.is_use(action)
            and await _hidden(workspace, [scope])
        ):
            return Decision(False, True, "hidden")
        return decision

    async def allowed_scope(self, scope: ModuleScope, **target: Any) -> bool:
        return (await self.decide_scope(scope, **target)).allowed

    async def require_scope(
        self,
        scope: ModuleScope,
        *,
        user: Any = None,
        workspace: str,
        action: str | None = None,
        feature: str | None = None,
        denied: str | None = None,
    ) -> None:
        """Raise ``AuthzDenied`` unless the user may use ``scope`` in ``workspace``."""
        decision = await self.decide_scope(
            scope, user=user, workspace=workspace, action=action, feature=feature
        )
        if decision.allowed:
            return
        if decision.reason == "hidden":
            raise AuthzDenied(403, detail=f"This {scope.type} is turned off in this workspace")
        raise await self._refusal(
            scope.action(action),
            decision,
            user=user,
            workspace=workspace,
            org=None,
            denied=denied or f"You may not use this {scope.type} here",
        )

    async def filter_scopes(
        self,
        items: Iterable[_T],
        *,
        user: Any = None,
        workspace: str,
        scope_of: Callable[[_T], ModuleScope | None],
        action: str | None = None,
        include_hidden: bool | Callable[[_T], Awaitable[bool]] = False,
        within_set: bool = False,
    ) -> list[_T]:
        """The items the user may use in ``workspace``, in order; an item with no
        module scope (``scope_of`` answers None) is kept: another check owns it.
        One the workspace turned off is left out unless ``include_hidden``: True
        for all, or a predicate asked of each hidden item (whether the caller may
        turn that one back on). ``within_set``: a listing of the workspace, which
        keeps only what its set holds, for everyone (``sets.within_set``)."""
        found = list(items)
        if within_set:
            from naas_abi.apps.nexus.apps.api.app.services.iam import sets

            found = await sets.within_set(found, workspace=workspace, scope_of=scope_of)
        scopes = [scope_of(item) for item in found]
        if not any(scopes):
            return found
        org = await self.org_of(workspace)
        if org is None:
            return [item for item, scope in zip(found, scopes, strict=True) if scope is None]
        ctx = self.context(user)
        by_action: dict[str, list[str]] = {}
        for scope in scopes:
            if scope is not None:
                by_action.setdefault(scope.action(action), []).append(
                    scope.resource(org, workspace)
                )

        def run() -> set[tuple[str, str]]:
            allowed: set[tuple[str, str]] = set()
            with use_call_context(ctx):
                for qualified, names in by_action.items():
                    allowed.update(
                        (qualified, name) for name in runtime.iam().filter(qualified, names).allowed
                    )
            return allowed

        allowed = await run_in_threadpool(run)
        kept = [
            (item, scope)
            for item, scope in zip(found, scopes, strict=True)
            if scope is None or (scope.action(action), scope.resource(org, workspace)) in allowed
        ]
        if include_hidden is True:
            return [item for item, _ in kept]
        hidden = await _hidden(
            workspace, [s for _, s in kept if s is not None and s.is_use(action)]
        )
        shown: list[_T] = []
        for item, scope in kept:
            if scope is None or scope not in hidden:
                shown.append(item)
            elif callable(include_hidden) and await include_hidden(item):
                shown.append(item)
        return shown

    async def scope_allowed_in_any(
        self,
        scope: ModuleScope,
        *,
        user: Any,
        workspaces: Sequence[tuple[str, str]],
        feature: str | None = None,
    ) -> str | None:
        """The first of ``workspaces`` (``(org, workspace)`` pairs) where the user
        may use ``scope`` and it is not turned off, else None."""
        ctx = self.context(user)

        def allows(org: str, workspace: str) -> bool:
            iam = runtime.iam()
            with use_call_context(ctx):
                if (
                    feature is not None
                    and not iam.authorize(
                        "nexus:UseFeature",
                        nexus_resource("feature", org=org, workspace=workspace, id=feature),
                    ).allowed
                ):
                    return False
                return iam.authorize(scope.action(), scope.resource(org, workspace)).allowed

        # Visibility is read only where IAM allows, until one answers.
        for org, workspace in workspaces:
            if await run_in_threadpool(allows, org, workspace) and not await _hidden(
                workspace, [scope]
            ):
                return workspace
        return None


AUTHZ = Authz()
require = AUTHZ.require
allowed = AUTHZ.allowed
allowed_ids = AUTHZ.allowed_ids
decide = AUTHZ.decide
filter_allowed = AUTHZ.filter
name = AUTHZ.name
require_scope = AUTHZ.require_scope
allowed_scope = AUTHZ.allowed_scope
filter_scopes = AUTHZ.filter_scopes

__all__ = [
    "AUTHZ",
    "ModuleScope",
    "NO_ORG",
    "TYPES_BY_NAME",
    "Authz",
    "AuthzDenied",
    "allowed",
    "allowed_ids",
    "decide",
    "filter_allowed",
    "name",
    "require",
    "require_scope",
    "allowed_scope",
    "filter_scopes",
]
