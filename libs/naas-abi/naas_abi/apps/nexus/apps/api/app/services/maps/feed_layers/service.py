"""Map layers on top of feeds: list, create, update, delete; a feed keeps one at least.

A feed without layers (new, or seeded before layers existed) gets its seeded
layers (re-applied when their seed revision goes up), or one default layer showing every feature — with the feed's id when
free, so ``?layer=<feed id>`` links keep working. Layers follow their feed's
availability (``services/maps/permissions``): a restricted feed's layers are not
listed, a shared feed's layers are listed read-only with ``shared_from``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import replace

from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
    MapsFeedLayerNotFoundError,
    MapsFeedLayerPolicyError,
    MapsFeedLayerValidationError,
    validate_feed_layer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.port import (
    MapsFeedLayerStorePort,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_OBJECT_STORAGE,
    MapsLayout,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.port import MapsSettingsStorePort
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.settings__schema import (
    MapsWorkspaceSettings,
    applied_revision,
)


def default_layer(feed: MapsLayout, taken: set[str]) -> MapsFeedLayer:
    """The layer a feed starts with: every feature, the feed's look."""
    layer_id = feed.id if feed.id not in taken else f"{feed.id[:44]}-all"
    return MapsFeedLayer(
        id=layer_id,
        feed_id=feed.id,
        title=feed.title,
        description=feed.description,
        color=feed.color,
        order=feed.order,
        system=feed.system,
    )


class MapsFeedLayerService:
    def __init__(
        self,
        store: MapsFeedLayerStorePort,
        settings: MapsSettingsStorePort,
        feeds: MapsLayoutService,
    ) -> None:
        self._store = store
        self._settings = settings
        self._feeds = feeds
        self._locks: dict[str, asyncio.Lock] = {}

    async def _ensure_layers(
        self,
        workspace_id: str,
        feeds: Sequence[MapsLayout],
        seeds: Sequence[MapsFeedLayer],
        revisions: Mapping[str, int],
    ) -> list[MapsFeedLayer]:
        """The workspace's stored layers, after syncing seeds and giving every feed one layer.

        Per feed: seeded layers whose revision is new are created, or overwrite
        their system copy (a deployment migration); once a feed has seeded
        layers, its automatic "every feature" default is dropped. A feed left
        with no layer gets that default.
        """
        feed_ids = {feed.id for feed in feeds}
        feed_seeds = [seed for seed in seeds if seed.feed_id in feed_ids]
        stored = await self._store.list(workspace_id)
        settings = await self._settings.get(workspace_id)

        def pending_of(settings: MapsWorkspaceSettings) -> list[MapsFeedLayer]:
            return [
                seed
                for seed in feed_seeds
                if revisions.get(seed.id, 1) > applied_revision(settings, "layer", seed.id)
            ]

        def bare(stored: list[MapsFeedLayer]) -> list[MapsLayout]:
            return [f for f in feeds if not any(layer.feed_id == f.id for layer in stored)]

        if not pending_of(settings) and not bare(stored):
            return stored
        lock = self._locks.setdefault(workspace_id, asyncio.Lock())
        async with lock:
            settings = await self._settings.get(workspace_id)
            by_id = {layer.id: layer for layer in await self._store.list(workspace_id)}
            pending = pending_of(settings)
            for seed in pending:
                existing = by_id.get(seed.id)
                if existing is not None and (
                    not existing.system or existing.feed_id != seed.feed_id
                ):
                    continue  # a custom layer took the id: leave it
                layer = replace(seed, system=True)
                await self._store.save(workspace_id, layer, user_id=None)
                by_id[layer.id] = layer
            seeded_feeds = {seed.feed_id for seed in feed_seeds}
            seed_ids = {seed.id for seed in feed_seeds}
            dropped = {
                layer.id
                for layer in by_id.values()
                if layer.system
                and layer.feed_id in seeded_feeds
                and layer.id not in seed_ids
                and not layer.class_labels
                and layer.id == layer.feed_id
            }
            for layer_id in dropped:
                await self._store.delete(workspace_id, layer_id)
                del by_id[layer_id]
            for feed in bare(list(by_id.values())):
                layer = default_layer(feed, set(by_id))
                await self._store.save(workspace_id, layer, user_id=None)
                by_id[layer.id] = layer
            if pending or dropped:
                await self._settings.save(
                    workspace_id,
                    settings.with_(
                        hidden_layouts=settings.hidden_layouts - dropped,
                        seed_revisions={
                            **settings.seed_revisions,
                            **{f"layer:{seed.id}": revisions.get(seed.id, 1) for seed in pending},
                        },
                    ),
                    user_id=None,
                )
            return list(by_id.values())

    async def list(
        self,
        workspace_id: str,
        *,
        seeds: Sequence[MapsFeedLayer] = (),
        revisions: Mapping[str, int] | None = None,
    ) -> list[MapsFeedLayer]:
        revisions = revisions or {}
        feeds = await self._feeds.visible(workspace_id)
        own = [feed for feed in feeds if not feed.shared_from]
        own_ids = {feed.id for feed in own}
        layers = [
            layer
            for layer in await self._ensure_layers(workspace_id, own, seeds, revisions)
            if layer.feed_id in own_ids
        ]
        taken = {layer.id for layer in layers}
        for feed in feeds:
            if not feed.shared_from:
                continue
            home = replace(feed, shared_from="")
            for layer in await self._ensure_layers(feed.shared_from, [home], seeds, revisions):
                if layer.feed_id == feed.id and layer.id not in taken:
                    layers.append(replace(layer, shared_from=feed.shared_from))
                    taken.add(layer.id)
        return sorted(layers, key=lambda layer: (layer.order, layer.title.lower()))

    async def get(self, workspace_id: str, layer_id: str) -> MapsFeedLayer:
        for layer in await self.list(workspace_id):
            if layer.id == layer_id:
                return layer
        raise MapsFeedLayerNotFoundError(f"Map layer {layer_id!r} not found")

    async def data_source(
        self, workspace_id: str, layer_id: str
    ) -> tuple[MapsFeedLayer, MapsLayout]:
        """A layer the workspace may use and its feed, when its data is a stored object."""
        layer = await self.get(workspace_id, layer_id)
        feed = await self._feeds.get(workspace_id, layer.feed_id)
        if feed.feed_type != FEED_OBJECT_STORAGE or not layer.storage_path:
            raise MapsFeedLayerNotFoundError(f"Map layer {layer_id!r} has no stored data")
        return layer, feed

    async def _own(self, workspace_id: str, layer_id: str) -> MapsFeedLayer | None:
        try:
            layer = await self.get(workspace_id, layer_id)
        except MapsFeedLayerNotFoundError:
            return None
        if layer.shared_from:
            raise MapsFeedLayerPolicyError(
                f"Map layer {layer_id!r} belongs to a feed shared from another workspace"
            )
        return layer

    async def save(
        self,
        workspace_id: str,
        layer: MapsFeedLayer,
        *,
        user_id: str | None,
        reserved: set[str] | frozenset[str] = frozenset(),
    ) -> MapsFeedLayer:
        layer = replace(
            layer,
            title=layer.title.strip(),
            description=layer.description.strip(),
            class_labels=tuple(dict.fromkeys(v.strip() for v in layer.class_labels if v.strip())),
            shared_from="",
        )
        errors = validate_feed_layer(layer, reserved=reserved)
        if errors:
            raise MapsFeedLayerValidationError(errors)
        feed = next(
            (f for f in await self._feeds.visible(workspace_id) if f.id == layer.feed_id), None
        )
        if feed is None:
            raise MapsFeedLayerValidationError([f"feed {layer.feed_id!r} not found"])
        if feed.shared_from:
            raise MapsFeedLayerPolicyError("This feed is shared from another workspace")
        existing = await self._own(workspace_id, layer.id)
        if existing is None and any(
            stored.id == layer.id for stored in await self._store.list(workspace_id)
        ):
            raise MapsFeedLayerValidationError([f"id {layer.id!r} is already used"])
        if existing is not None and existing.feed_id != layer.feed_id:
            raise MapsFeedLayerValidationError(["a layer cannot move to another feed"])
        layer = replace(layer, system=bool(existing and existing.system))
        if existing is not None and existing.system:
            # A seeded layer's object belongs to the seed (Settings edits metadata only).
            layer = replace(layer, storage_path=existing.storage_path)
        elif not layer.storage_path and feed.feed_type == FEED_OBJECT_STORAGE:
            # A layer added to a stored feed reads the feed's object, filtered by its types.
            siblings = [
                s for s in await self.list(workspace_id) if s.feed_id == feed.id and s.storage_path
            ]
            if siblings:
                layer = replace(
                    layer, storage_path=min(siblings, key=lambda s: s.order).storage_path
                )
        await self._store.save(workspace_id, layer, user_id=user_id)
        return layer

    async def _forget(self, workspace_id: str, layer_ids: set[str]) -> None:
        settings = await self._settings.get(workspace_id)
        if layer_ids & (settings.hidden_layouts | set(settings.layer_colors)):
            await self._settings.save(
                workspace_id,
                settings.with_(
                    hidden_layouts=settings.hidden_layouts - layer_ids,
                    layer_colors={
                        k: v for k, v in settings.layer_colors.items() if k not in layer_ids
                    },
                ),
                user_id=None,
            )

    async def delete(self, workspace_id: str, layer_id: str) -> None:
        existing = await self._own(workspace_id, layer_id)
        if existing is None:
            raise MapsFeedLayerNotFoundError(f"Map layer {layer_id!r} not found")
        if existing.system:
            raise MapsFeedLayerPolicyError(
                f"Map layer {layer_id!r} is provided by the deployment: hide it instead"
            )
        siblings = [
            layer
            for layer in await self._store.list(workspace_id)
            if layer.feed_id == existing.feed_id
        ]
        if len(siblings) <= 1:
            raise MapsFeedLayerPolicyError(
                "A feed needs at least one layer: delete the feed instead"
            )
        await self._store.delete(workspace_id, layer_id)
        await self._forget(workspace_id, {layer_id})

    async def delete_feed(self, workspace_id: str, feed_id: str) -> None:
        """Delete a feed (its own rules apply) and every layer on it."""
        await self._feeds.delete(workspace_id, feed_id)
        gone = {
            layer.id for layer in await self._store.list(workspace_id) if layer.feed_id == feed_id
        }
        for layer_id in gone:
            await self._store.delete(workspace_id, layer_id)
        await self._forget(workspace_id, gone)
