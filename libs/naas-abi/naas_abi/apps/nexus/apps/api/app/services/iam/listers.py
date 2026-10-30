"""What naas_abi lists for the policy builder (core ``services/iam/AGENTS.md``,
"Publishers and listing").

naas_abi publishes the ``nexus`` catalog and lists, as candidates IAM filters as
the caller: its organizations and workspaces (labels for the containers IAM
lists from its registry), their members, the features the deployment enables
(only those in ``enabled_features``: a disabled one exists nowhere), and the
agents, apps, workflows and pipelines of every module (the ``module`` catalog,
``modules/scopes.py``), named in the container asked.

IAM is synchronous and Nexus's database asynchronous: each lister runs its query
on the API's event loop (``OnLoop``), from IAM's thread. Asked from that loop
itself it fails, which IAM reports as wildcards (it never blocks the loop).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import names
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.listing import (
    ListedPage,
    ListedResource,
    ListingQuery,
    ResourceLister,
    page_of,
)
from naas_abi_core.services.iam.names import PLATFORM

Source = Callable[[ListingQuery], Awaitable[list[ListedResource]]]
# How long one listing waits for the database, and how long the modules' items
# (gathered from the engine, discovery and the jobs) are reused.
TIMEOUT_SECONDS = 10.0
MODULES_SECONDS = 30.0


class OnLoop(ResourceLister):
    """A lister over an async source, run on ``loop`` (the API's)."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        source: Source,
        *,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._loop, self._source, self._timeout = loop, source, timeout

    def list_resources(self, query: ListingQuery) -> ListedPage:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            raise RuntimeError("A Nexus lister cannot wait on the loop it runs on")
        future = asyncio.run_coroutine_threadsafe(self._source(query), self._loop)
        try:
            return page_of(future.result(self._timeout), query)
        except BaseException:
            future.cancel()
            raise


async def organizations(query: ListingQuery) -> list[ListedResource]:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(OrganizationModel.id, OrganizationModel.name))).all()
    return [
        ListedResource(names.org_container(org_id), org_id, label=name or "")
        for org_id, name in rows
    ]


async def workspaces(query: ListingQuery) -> list[ListedResource]:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
    from sqlalchemy import select

    statement = select(WorkspaceModel.id, WorkspaceModel.name, WorkspaceModel.organization_id)
    org = names.org_of(query.container)
    if org is not None:
        statement = statement.where(WorkspaceModel.organization_id == org)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(statement)).all()
    return [
        ListedResource(names.workspace_container(org_id, ws_id), ws_id, label=name or "")
        for ws_id, name, org_id in rows
    ]


async def members(query: ListingQuery) -> list[ListedResource]:
    """The members of the organizations and workspaces in the container asked:
    ``<org>/nexus:member/<user>`` and ``<workspace>/nexus:member/<user>``."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import (
        OrganizationMemberModel,
        UserModel,
        WorkspaceMemberModel,
        WorkspaceModel,
    )
    from sqlalchemy import select

    org, workspace = names.org_of(query.container), names.workspace_of(query.container)
    found: list[ListedResource] = []
    async with AsyncSessionLocal() as db:
        if workspace is None:
            orgs = select(
                OrganizationMemberModel.organization_id,
                OrganizationMemberModel.user_id,
                UserModel.email,
                UserModel.name,
            ).join(UserModel, UserModel.id == OrganizationMemberModel.user_id)
            if org is not None:
                orgs = orgs.where(OrganizationMemberModel.organization_id == org)
            for org_id, user_id, email, name in (await db.execute(orgs)).all():
                found.append(
                    ListedResource(
                        names.nexus_resource(
                            "member", container=names.org_container(org_id), id=user_id
                        ),
                        user_id,
                        label=name or email or "",
                        description=email or "",
                    )
                )
        spaces = (
            select(
                WorkspaceMemberModel.workspace_id,
                WorkspaceModel.organization_id,
                WorkspaceMemberModel.user_id,
                UserModel.email,
                UserModel.name,
            )
            .join(WorkspaceModel, WorkspaceModel.id == WorkspaceMemberModel.workspace_id)
            .join(UserModel, UserModel.id == WorkspaceMemberModel.user_id)
        )
        if workspace is not None:
            spaces = spaces.where(WorkspaceMemberModel.workspace_id == workspace)
        elif org is not None:
            spaces = spaces.where(WorkspaceModel.organization_id == org)
        for ws_id, org_id, user_id, email, name in (await db.execute(spaces)).all():
            found.append(
                ListedResource(
                    names.nexus_resource(
                        "member",
                        container=names.workspace_container(org_id, ws_id),
                        id=user_id,
                    ),
                    user_id,
                    label=name or email or "",
                    description=email or "",
                )
            )
    return found


def enabled_features() -> list[str]:
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import enabled_feature_catalog
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    return enabled_feature_catalog(live_settings().feature_flags)


def feature_items(container: str, enabled: list[str]) -> list[ListedResource]:
    """The features the deployment enables, in ``container`` (an organization's
    or a workspace's, where a feature is used); none at the platform."""
    if container == PLATFORM:
        return []
    return [
        ListedResource(names.nexus_resource("feature", container=container, id=key), key, key)
        for key in enabled
    ]


async def features(query: ListingQuery) -> list[ListedResource]:
    return feature_items(query.container, enabled_features())


class ModuleItems:
    """The modules' agents, apps, workflows and pipelines (``scopes.gather``),
    reused for ``MODULES_SECONDS``, each named in the container asked."""

    def __init__(self, gather: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None):
        self._gather = gather
        self._cached: tuple[float, list[dict[str, Any]]] | None = None
        self._lock = threading.Lock()

    async def modules(self) -> list[dict[str, Any]]:
        """``scopes.gather``'s entries, read at most once per ``MODULES_SECONDS``."""
        now = time.monotonic()
        with self._lock:
            cached = self._cached
        if cached is not None and now - cached[0] < MODULES_SECONDS:
            return cached[1]
        if self._gather is not None:
            found = await self._gather()
        else:
            from naas_abi.apps.nexus.apps.api.app.services.modules import scopes

            found = await scopes.gather()
        with self._lock:
            self._cached = (now, found)
        return found

    def source(self, type_name: str) -> Source:
        from naas_abi.apps.nexus.apps.api.app.services.modules.scopes import PLURAL

        plural = PLURAL[type_name]

        async def items(query: ListingQuery) -> list[ListedResource]:
            found: list[ListedResource] = []
            for entry in await self.modules():
                module = entry["module"]
                if query.module and module != query.module:
                    continue
                for item in entry.get(plural) or ():
                    found.append(
                        ListedResource(
                            module_scopes.scope_resource(
                                type_name, module, item["name"], container=query.container
                            ),
                            f"{module}/{item['name']}",
                            label=item.get("display_name") or item["name"],
                            description=item.get("description") or "",
                        )
                    )
            return found

        return items


# The modules' items this process lists: the listers' and the policy builder's
# publishers (``iam_admin``) share one read of the modules.
MODULE_ITEMS = ModuleItems()


def listers(loop: asyncio.AbstractEventLoop) -> dict[tuple[str, str], ResourceLister]:
    """naas_abi's listers, by ``(service, type)``, their queries run on ``loop``."""
    modules = MODULE_ITEMS
    found: dict[tuple[str, str], ResourceLister] = {
        (names.SERVICE, names.ORGANIZATION): OnLoop(loop, organizations),
        (names.SERVICE, names.WORKSPACE): OnLoop(loop, workspaces),
        (names.SERVICE, "member"): OnLoop(loop, members),
        (names.SERVICE, "feature"): OnLoop(loop, features),
    }
    for type_name in module_scopes.TYPES:
        found[(module_scopes.SERVICE, type_name)] = OnLoop(
            loop, modules.source(type_name), timeout=TIMEOUT_SECONDS * 3
        )
    return found


async def register() -> list[tuple[str, str]]:
    """Register naas_abi's listers with the engine's IAM, at start."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
    from naas_abi_core.services.iam.kernel_catalogs import register_listers

    found = listers(asyncio.get_running_loop())

    class _Offer:
        def iam_listers(self) -> dict[tuple[str, str], ResourceLister]:
            return found

    return register_listers(runtime.iam(), [_Offer()])


__all__ = ["OnLoop", "listers", "register", "feature_items", "ModuleItems", "MODULE_ITEMS"]
