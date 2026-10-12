"""Workspace basemaps: list (seeding on first use), create, update, delete, hide, preview.

Policy: seeded basemaps (``system``) can be renamed, reordered, restyled,
hidden and given a new preview, but not deleted. Custom basemaps can be
deleted; their hidden flag goes with them. Which workspaces may use a seeded
or shared basemap is decided by ``services/maps/permissions``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace

from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    BASEMAP_ID_PATTERN,
    CATEGORIES,
    MapsBasemap,
    MapsBasemapList,
    MapsBasemapNotFoundError,
    MapsBasemapPolicyError,
    MapsBasemapPreview,
    MapsBasemapValidationError,
    validate_basemap,
    validate_preview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.port import MapsBasemapStorePort
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_BASEMAP,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import (
    MapsAccess,
    MapsPolicy,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.port import MapsSettingsStorePort

# A seed as (definition, preview); see services/maps/seeds.py.
SeedLike = tuple[MapsBasemap, MapsBasemapPreview | None]


def _order_key(basemap: MapsBasemap) -> tuple[int, int, str]:
    column = CATEGORIES.index(basemap.category) if basemap.category in CATEGORIES else 99
    return (column, basemap.order, basemap.title.lower())


class MapsBasemapService:
    def __init__(
        self,
        store: MapsBasemapStorePort,
        settings: MapsSettingsStorePort,
        access: MapsAccess | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._access = access or MapsAccess(InMemoryMapsGrantStore())
        self._seed_locks: dict[str, asyncio.Lock] = {}

    async def ensure_seeded(self, workspace_id: str, seeds: Sequence[SeedLike]) -> None:
        """Copy basemap seeds the workspace has never received (once per seed id)."""
        settings = await self._settings.get(workspace_id)
        if not any(basemap.id not in settings.seeded_basemaps for basemap, _ in seeds):
            return
        lock = self._seed_locks.setdefault(workspace_id, asyncio.Lock())
        async with lock:
            settings = await self._settings.get(workspace_id)
            pending = [(b, p) for b, p in seeds if b.id not in settings.seeded_basemaps]
            if not pending:
                return
            stored = {basemap.id for basemap in await self._store.list(workspace_id)}
            for basemap, preview in pending:
                if basemap.id in stored:
                    continue
                await self._store.save(workspace_id, replace(basemap, system=True), user_id=None)
                if preview is not None:
                    await self._store.set_preview(workspace_id, basemap.id, preview, user_id=None)
            await self._settings.save(
                workspace_id,
                settings.with_(
                    seeded_basemaps=settings.seeded_basemaps | {b.id for b, _ in pending}
                ),
                user_id=None,
            )

    async def _visible(self, workspace_id: str, policy: MapsPolicy) -> list[MapsBasemap]:
        own = [
            basemap
            for basemap in await self._store.list(workspace_id)
            if not basemap.system or policy.allows(basemap.id, DEPLOYMENT, workspace_id)
        ]
        taken = {basemap.id for basemap in own}
        by_owner: dict[str, list[MapsBasemap]] = {}
        shared: list[MapsBasemap] = []
        for grant in policy.shared_into(workspace_id):
            if grant.item_id in taken:
                continue
            if grant.owner not in by_owner:
                by_owner[grant.owner] = await self._store.list(grant.owner)
            for basemap in by_owner[grant.owner]:
                if basemap.id == grant.item_id and not basemap.system:
                    shared.append(replace(basemap, shared_from=grant.owner))
                    taken.add(basemap.id)
        return own + shared

    async def list(self, workspace_id: str, *, seeds: Sequence[SeedLike] = ()) -> MapsBasemapList:
        policy = await self._access.policy(KIND_BASEMAP)
        allowed = [(b, p) for b, p in seeds if policy.allows(b.id, DEPLOYMENT, workspace_id)]
        if allowed:
            await self.ensure_seeded(workspace_id, allowed)
        basemaps = sorted(await self._visible(workspace_id, policy), key=_order_key)
        settings = await self._settings.get(workspace_id)
        return MapsBasemapList(basemaps=basemaps, hidden=set(settings.hidden_basemaps))

    async def get(self, workspace_id: str, basemap_id: str) -> MapsBasemap:
        """A basemap the workspace may use: its own, or one shared with it."""
        policy = await self._access.policy(KIND_BASEMAP)
        for basemap in await self._visible(workspace_id, policy):
            if basemap.id == basemap_id:
                return basemap
        raise MapsBasemapNotFoundError(f"Basemap {basemap_id!r} not found")

    async def _find(self, workspace_id: str, basemap_id: str) -> MapsBasemap | None:
        """The workspace's own basemap (shared ones are read-only here)."""
        try:
            basemap = await self.get(workspace_id, basemap_id)
        except MapsBasemapNotFoundError:
            return None
        if basemap.shared_from:
            raise MapsBasemapPolicyError(
                f"Basemap {basemap_id!r} is shared from another workspace: edit it there"
            )
        return basemap

    async def save(
        self, workspace_id: str, basemap: MapsBasemap, *, user_id: str | None
    ) -> MapsBasemap:
        existing = await self._find(workspace_id, basemap.id)
        if existing is None and any(
            stored.id == basemap.id and stored.system
            for stored in await self._store.list(workspace_id)
        ):
            raise MapsBasemapValidationError(
                [f"id {basemap.id!r} is taken by a deployment basemap"]
            )
        # system and preview metadata belong to the store, never to the request.
        basemap = replace(
            basemap,
            shared_from="",
            title=basemap.title.strip(),
            system=bool(existing and existing.system),
            preview_content_type=existing.preview_content_type if existing else None,
            preview_version=existing.preview_version if existing else 0,
        )
        errors = validate_basemap(basemap)
        if errors:
            raise MapsBasemapValidationError(errors)
        await self._store.save(workspace_id, basemap, user_id=user_id)
        return basemap

    async def delete(self, workspace_id: str, basemap_id: str) -> None:
        existing = await self._find(workspace_id, basemap_id)
        if existing is None:
            raise MapsBasemapNotFoundError(f"Basemap {basemap_id!r} not found")
        if existing.system:
            raise MapsBasemapPolicyError(
                f"Basemap {basemap_id!r} is provided by the deployment: hide it instead"
            )
        await self._store.delete(workspace_id, basemap_id)
        await self._access.forget(KIND_BASEMAP, basemap_id, workspace_id)
        settings = await self._settings.get(workspace_id)
        if basemap_id in settings.hidden_basemaps:
            await self._settings.save(
                workspace_id,
                settings.with_(hidden_basemaps=settings.hidden_basemaps - {basemap_id}),
                user_id=None,
            )

    async def set_hidden(
        self, workspace_id: str, basemap_id: str, hidden: bool, *, user_id: str | None
    ) -> set[str]:
        if not BASEMAP_ID_PATTERN.match(basemap_id):
            raise MapsBasemapValidationError(["invalid basemap id"])
        settings = await self._settings.get(workspace_id)
        current = settings.hidden_basemaps
        updated = current | {basemap_id} if hidden else current - {basemap_id}
        if updated != current:
            await self._settings.save(
                workspace_id, settings.with_(hidden_basemaps=updated), user_id=user_id
            )
        return set(updated)

    async def get_preview(self, workspace_id: str, basemap_id: str) -> MapsBasemapPreview:
        basemap = await self.get(workspace_id, basemap_id)
        preview = await self._store.get_preview(basemap.shared_from or workspace_id, basemap_id)
        if preview is None:
            raise MapsBasemapNotFoundError(f"Basemap {basemap_id!r} has no preview")
        return preview

    async def set_preview(
        self,
        workspace_id: str,
        basemap_id: str,
        content_type: str,
        content: bytes,
        *,
        user_id: str | None,
    ) -> MapsBasemap:
        basemap = await self._find(workspace_id, basemap_id)
        if basemap is None:
            raise MapsBasemapNotFoundError(f"Basemap {basemap_id!r} not found")
        errors = validate_preview(content_type, content)
        if errors:
            raise MapsBasemapValidationError(errors)
        preview = MapsBasemapPreview(
            content_type=content_type.split(";", 1)[0].strip().lower(), content=content
        )
        version = await self._store.set_preview(workspace_id, basemap_id, preview, user_id=user_id)
        return replace(basemap, preview_content_type=preview.content_type, preview_version=version)
