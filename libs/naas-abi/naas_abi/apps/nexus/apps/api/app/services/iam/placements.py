"""Which workspace owns the kernel resources Nexus keeps for it.

A kernel service names a resource inside the container IAM *placed* it in (a
workspace's, ``abi:nexus:organization/<org>/nexus:workspace/<ws>``). Nexus places what it creates for a workspace (its files' prefix, its
graphs, its datasets, its repositories) the moment it creates it, and a domain
registers a ``placement_source`` for what already exists, which ``place_existing``
applies at every startup (it only writes what differs).

    @placement_source
    async def workspace_prefixes(db) -> Iterable[Placement]:
        rows = await db.execute(text("SELECT id FROM workspaces"))
        return [Placement("object_storage", ("workspaces", ws), ws, prefix=True) for ws, in rows]

A resource nobody placed belongs to the platform: no workspace role reaches it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container, workspace_of
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.names import IdKind, encode_id
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool


@dataclass(frozen=True)
class Placement:
    """``parts`` of ``service``'s resource (or of every resource below it, with
    ``prefix``) belong to ``workspace``."""

    service: str
    parts: tuple[str, ...] | str
    workspace: str
    prefix: bool = False
    kind: IdKind = "path"

    def id_key(self) -> str:
        key = encode_id(self.parts, self.kind)
        if not self.prefix:
            return key
        return f"{key}/*" if self.kind == "path" else f"{key}*"


PlacementSource = Callable[[AsyncSession], Awaitable[Iterable[Placement]]]
SOURCES: list[PlacementSource] = []
# What a new workspace needs, for that workspace alone (no scan of the others).
WorkspaceHook = Callable[[AsyncSession, str], Awaitable[Iterable[Placement]]]
WORKSPACE_HOOKS: list[WorkspaceHook] = []


def placement_source(source: PlacementSource) -> PlacementSource:
    """Register what a domain already owns, for ``place_existing``."""
    SOURCES.append(source)
    return source


def on_workspace_created(hook: WorkspaceHook) -> WorkspaceHook:
    """Register what one new workspace gets: ``await hook(db, workspace_id)`` returns
    its placements (and may apply what else IAM must hold for it)."""
    WORKSPACE_HOOKS.append(hook)
    return hook


async def place_new_workspace(db: AsyncSession, workspace_id: str) -> int:
    """Place the resources of one new workspace: only the registered hooks run,
    for that workspace. Errors of one hook never stop the others."""
    found: list[Placement] = []
    for hook in list(WORKSPACE_HOOKS):
        try:
            found.extend(await hook(db, workspace_id))
        except Exception:  # noqa: BLE001 - one domain's resources never block the rest
            logger.exception(f"Workspace hook {hook.__name__} failed for {workspace_id}")
    return await place_many(found)


async def place(placement: Placement, *, org: str | None = None) -> None:
    """Place one resource (or prefix) in its workspace, as ``api``."""
    await place_many([placement], org=org)


async def place_many(placements: Sequence[Placement], *, org: str | None = None) -> int:
    """Place resources in their workspaces' containers; returns how many were
    written. ``org``: the organization of every workspace named (skips the
    lookup). A placement that already says the same is left alone, and one of a
    workspace IAM does not know is skipped (logged)."""
    containers: dict[str, str | None] = {}
    entries = []
    for placement in placements:
        if placement.workspace not in containers:
            containers[placement.workspace] = (
                workspace_container(org, placement.workspace)
                if org is not None
                else await AUTHZ.container_of(placement.workspace)
            )
        container = containers[placement.workspace]
        if container is None:
            logger.warning(f"Not placed: workspace {placement.workspace} is unknown to IAM")
            continue
        entries.append((placement, container))

    def work() -> int:
        iam = runtime.iam()
        written = 0
        with as_service_account("api"):
            known: dict[str, dict[str, str]] = {}
            for placement, container in entries:
                if placement.service not in known:
                    known[placement.service] = {
                        p.id_key: p.container for p in iam.list_placements(placement.service)
                    }
                key = placement.id_key()
                if known[placement.service].get(key) == container:
                    continue
                iam.put_placement(placement.service, key, container)
                known[placement.service][key] = container
                written += 1
        return written

    return await run_in_threadpool(work)


async def forget(placement: Placement) -> None:
    """Drop the placement of a resource that was deleted."""

    def work() -> None:
        with as_service_account("api"):
            runtime.iam().delete_placement(placement.service, placement.id_key())

    await run_in_threadpool(work)


async def forget_workspace(workspace_id: str) -> int:
    """Drop every placement in a workspace whose creation was undone; returns
    how many."""

    def work() -> int:
        iam = runtime.iam()
        with as_service_account("api"):
            found = [p for p in iam.list_placements() if workspace_of(p.container) == workspace_id]
            for placement in found:
                iam.delete_placement(placement.service, placement.id_key)
        return len(found)

    return await run_in_threadpool(work)


async def place_existing(db: AsyncSession) -> int:
    """Apply every registered source; errors of one source never stop the others."""
    found: list[Placement] = []
    for source in list(SOURCES):
        try:
            found.extend(await source(db))
        except Exception:  # noqa: BLE001 - one domain's rows never block the rest
            logger.exception(f"Placement source {source.__name__} failed")
    written = await place_many(found)
    logger.info(f"Kernel resources placed in their workspaces: {written} written of {len(found)}")
    return written


def placements_of(items: Iterable[Any]) -> list[Placement]:
    return [item for item in items if isinstance(item, Placement)]
