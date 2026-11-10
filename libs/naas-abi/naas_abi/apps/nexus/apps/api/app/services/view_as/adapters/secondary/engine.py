"""``ViewIam`` on the engine's IAM, in process, as the viewer: ``api`` on behalf of the
viewer, with the IAM groups their session maps to, so the viewer's own rights bound
the call (``api`` holds ``iam:ViewAs`` only for them). Never ``api`` for no user: that
account would view as anyone but a platform admin.

The workspace is the container of the check. Memberships say which workspaces the
person belongs to: a role held there, or the organization-wide role an organization's
owner or admin holds below it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, Authz
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, Memberships
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_of
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import Viewer, ViewIam
from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    CallContext,
    Principal,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.IAMPorts import ViewAsVerdict
from naas_abi_core.services.iam.IAMService import view_as_resource
from starlette.concurrency import run_in_threadpool

NEXUS_IDENTITY = "api"
_T = TypeVar("_T")


def viewer_context(viewer: Viewer) -> CallContext:
    """``api`` on behalf of the viewer, with the groups of their session."""
    return replace(
        ANONYMOUS,
        principal=service_account(NEXUS_IDENTITY),
        on_behalf_of=Principal(id=viewer.user_id, kind="user", groups=frozenset(viewer.group_ids)),
        triggered_via="api",
    )


class ViewAsSecondaryAdapterEngine(ViewIam):
    def __init__(self, memberships: Memberships = MEMBERSHIPS, authz: Authz = AUTHZ) -> None:
        self._memberships = memberships
        self._authz = authz

    async def _as(self, viewer: Viewer, work: Callable[[Any], _T]) -> _T:
        context = viewer_context(viewer)

        def run() -> _T:
            with use_call_context(context):
                return work(runtime.iam())

        return await run_in_threadpool(run)

    async def candidates(self, user_id: str) -> list[str]:
        found = {workspace for _, workspace in await self._memberships.workspaces_of(user_id)}
        for org in await self._memberships.org_wide_orgs_of(user_id):
            for container in await self._memberships.containers_in(org):
                workspace = workspace_of(container)
                if workspace is not None and container.startswith(org_container(org) + "/"):
                    found.add(workspace)
        return sorted(found)

    async def container_of(self, workspace_id: str) -> str | None:
        return await self._authz.container_of(workspace_id)

    async def verdict(
        self, viewer: Viewer, principal_id: str, container: str, groups: tuple[str, ...]
    ) -> ViewAsVerdict:
        return await self._as(
            viewer, lambda iam: iam.view_as_verdict(principal_id, container, groups)
        )

    async def require(
        self, viewer: Viewer, principal_id: str, container: str, groups: tuple[str, ...]
    ) -> None:
        await self._as(viewer, lambda iam: iam.require_view_as(principal_id, container, groups))

    async def allows(self, viewer: Viewer, principal_id: str, container: str) -> bool:
        resource = view_as_resource(principal_id, container)
        return await self._as(viewer, lambda iam: iam.authorize("iam:ViewAs", resource).allowed)
