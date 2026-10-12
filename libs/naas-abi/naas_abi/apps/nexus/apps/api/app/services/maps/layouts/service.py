"""Workspace Maps layers: SPARQL and feed layers, visibility and colors.

A SPARQL layout's query runs through the workspace-scoped graph store, so it
reads only what the workspace may read. Queries are validated on save: SELECT
only, no SERVICE / FROM (the dataset is the workspace's), and ?label ?lat ?lng
projected. A feed layout points at a path on the Nexus API; the web proxy
calls it with the member's token, so only same-host paths are accepted.

Deployment seeds (``services/maps/seeds.py``) are copied into a workspace the
first time its layers are listed, when the workspace may use them
(``services/maps/permissions``); they are marked ``system`` and can be edited
and hidden but not deleted. A workspace's own records can be shared with other
workspaces, where they are listed read-only with ``shared_from``.
"""

from __future__ import annotations

import asyncio
import builtins
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
    query_shape,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    CATEGORY_PATTERN,
    COLOR_PATTERN,
    FEED_GEOJSON_URL,
    FEED_SPARQL,
    FEED_TYPES,
    LAYOUT_ID_PATTERN,
    MAX_PINS,
    MAX_QUERY_LENGTH,
    MAX_URL_LENGTH,
    REQUIRED_VARIABLES,
    MapsLayout,
    MapsLayoutList,
    MapsLayoutNotFoundError,
    MapsLayoutPolicyError,
    MapsLayoutValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.port import MapsLayoutStorePort
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_LAYOUT,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import (
    MapsAccess,
    MapsPolicy,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.port import MapsSettingsStorePort
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.settings__schema import (
    MapsWorkspaceSettings,
    applied_revision,
)
from rdflib.plugins.sparql import prepareQuery

_LIMIT_AT_END = re.compile(r"\bLIMIT\s+\d+\s*(OFFSET\s+\d+\s*)?$", re.IGNORECASE)


def _projected(sparql: str) -> set[str]:
    return {str(v) for v in prepareQuery(sparql).algebra.get("PV") or []}


def is_nexus_api_path(value: str) -> bool:
    """Same-host API path: the web proxy forwards the member's Bearer token to it."""
    return (
        value.startswith("/api/")
        and "//" not in value
        and ".." not in value
        and "\\" not in value
        and not any(ch.isspace() for ch in value)
        and len(value) <= MAX_URL_LENGTH
    )


def _is_logo_url(value: str) -> bool:
    if len(value) > MAX_URL_LENGTH or any(ch.isspace() for ch in value):
        return False
    return value.startswith("https://") or (value.startswith("/") and not value.startswith("//"))


def validate_layout(
    layout: MapsLayout, *, reserved: set[str] | frozenset[str] = frozenset()
) -> list[str]:
    """Human-readable errors; empty when the layout can be saved."""
    errors: list[str] = []
    if not LAYOUT_ID_PATTERN.match(layout.id):
        errors.append("id must be lowercase letters, digits and dashes (max 48)")
    elif layout.id in reserved:
        errors.append(f"id {layout.id!r} is taken by a built-in layout")
    if not layout.title.strip():
        errors.append("title is required")
    if not COLOR_PATTERN.match(layout.color):
        errors.append("color must be a #rrggbb hex value")
    if not CATEGORY_PATTERN.match(layout.category):
        errors.append("category must be lowercase letters, digits and dashes")
    if layout.logo_url and not _is_logo_url(layout.logo_url):
        errors.append("logo_url must be an https:// URL or a path starting with /")
    if layout.basemap_id and not LAYOUT_ID_PATTERN.match(layout.basemap_id):
        errors.append("basemap_id must be a basemap id")
    if layout.fit_max_zoom is not None and not 1 <= layout.fit_max_zoom <= 19:
        errors.append("fit_max_zoom must be between 1 and 19")
    if layout.feed_type not in FEED_TYPES:
        errors.append("feed_type must be one of " + ", ".join(sorted(FEED_TYPES)))
        return errors
    if layout.feed_type == FEED_GEOJSON_URL:
        if not is_nexus_api_path(layout.feed_url):
            errors.append("feed_url must be a Nexus API path starting with /api/ (no host, no ..)")
        return errors
    query = layout.query.strip()
    if not query:
        errors.append("query is required")
        return errors
    if len(query) > MAX_QUERY_LENGTH:
        errors.append(f"query is too long (max {MAX_QUERY_LENGTH} characters)")
        return errors
    try:
        kind, _ = query_shape(query)
    except GraphAccessError:
        errors.append(
            "SERVICE and FROM clauses are not allowed: queries run on the workspace graphs"
        )
        return errors
    except Exception as exc:  # noqa: BLE001 - the parser's message is what the author needs
        errors.append(f"invalid SPARQL ({exc})")
        return errors
    if kind != "SelectQuery":
        errors.append("query must be a SELECT")
        return errors
    missing = REQUIRED_VARIABLES - _projected(query)
    if missing:
        errors.append("query must project " + ", ".join("?" + v for v in sorted(missing)))
    return errors


def _with_limit(query: str) -> str:
    """Cap the rows a layout can pull; keep an author's own LIMIT if it is there."""
    stripped = query.strip()
    return stripped if _LIMIT_AT_END.search(stripped) else f"{stripped}\nLIMIT {MAX_PINS}"


def _coordinate(value: str, bound: float) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) and -bound <= number <= bound else None


def pin_to_feature(pin: dict[str, Any]) -> dict[str, Any]:
    """Maps pin dict → GeoJSON Point feature (properties hold Nexus fields)."""
    lat, lng = pin["lat"], pin["lng"]
    props = {k: v for k, v in pin.items() if k not in ("lat", "lng")}
    feature: dict[str, Any] = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": props,
    }
    if (fid := props.pop("id", None)) is not None:
        feature["id"] = fid
    return feature


def maps_feed_payload(features: list[dict[str, Any]], **meta: Any) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features, "count": len(features), **meta}


def rows_to_pins(layout: MapsLayout, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pins in the Maps feed shape; rows without valid coordinates are skipped."""
    pins: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:MAX_PINS]):
        lat_cell, lng_cell, label_cell = row.get("lat"), row.get("lng"), row.get("label")
        if lat_cell is None or lng_cell is None or label_cell is None:
            continue
        lat = _coordinate(lat_cell.value, 90)
        lng = _coordinate(lng_cell.value, 180)
        if lat is None or lng is None:
            continue
        uri_cell = row.get("uri")
        uri = uri_cell.value if uri_cell is not None and uri_cell.is_uri else None
        pin: dict[str, Any] = {
            "id": f"{layout.id}:{uri or index}",
            "lat": lat,
            "lng": lng,
            "label": label_cell.value,
            "color": layout.color,
        }
        if uri:
            pin["entityUri"] = uri
        if (graph := row.get("graph")) is not None and graph.is_uri:
            pin["graphUri"] = graph.value
        if (detail := row.get("detail")) is not None and detail.value:
            pin["detail"] = detail.value
        pins.append(pin)
    return pins


class MapsLayoutService:
    def __init__(
        self,
        store: MapsLayoutStorePort,
        settings: MapsSettingsStorePort,
        access: MapsAccess | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._access = access or MapsAccess(InMemoryMapsGrantStore())
        self._seed_locks: dict[str, asyncio.Lock] = {}

    async def ensure_seeded(
        self,
        workspace_id: str,
        seeds: Sequence[MapsLayout],
        revisions: Mapping[str, int] | None = None,
    ) -> None:
        """Copy deployment seeds into the workspace; re-apply those whose revision went up.

        A seed is applied once per revision: a new seed creates its record, a
        higher revision overwrites the workspace's system copy (a deployment
        migration). A custom record that took the same id is never touched.
        """
        revisions = revisions or {}

        def pending_of(settings: MapsWorkspaceSettings) -> list[MapsLayout]:
            return [
                seed
                for seed in seeds
                if revisions.get(seed.id, 1) > applied_revision(settings, "layout", seed.id)
            ]

        if not pending_of(await self._settings.get(workspace_id)):
            return
        lock = self._seed_locks.setdefault(workspace_id, asyncio.Lock())
        async with lock:
            settings = await self._settings.get(workspace_id)
            pending = pending_of(settings)
            if not pending:
                return
            stored = {layout.id: layout for layout in await self._store.list(workspace_id)}
            for seed in pending:
                existing = stored.get(seed.id)
                if existing is None or existing.system:
                    await self._store.save(workspace_id, replace(seed, system=True), user_id=None)
            await self._settings.save(
                workspace_id,
                settings.with_(
                    seeded_layouts=settings.seeded_layouts | {seed.id for seed in pending},
                    seed_revisions={
                        **settings.seed_revisions,
                        **{f"layout:{seed.id}": revisions.get(seed.id, 1) for seed in pending},
                    },
                ),
                user_id=None,
            )

    async def _own(self, workspace_id: str, policy: MapsPolicy) -> list[MapsLayout]:
        """The workspace's records, minus deployment items it may no longer use."""
        return [
            layout
            for layout in await self._store.list(workspace_id)
            if not layout.system or policy.allows(layout.id, DEPLOYMENT, workspace_id)
        ]

    async def _visible(self, workspace_id: str, policy: MapsPolicy) -> list[MapsLayout]:
        own = await self._own(workspace_id, policy)
        taken = {layout.id for layout in own}
        by_owner: dict[str, list[MapsLayout]] = {}
        shared: list[MapsLayout] = []
        for grant in policy.shared_into(workspace_id):
            if grant.item_id in taken:
                continue
            if grant.owner not in by_owner:
                by_owner[grant.owner] = await self._store.list(grant.owner)
            for layout in by_owner[grant.owner]:
                if layout.id == grant.item_id and not layout.system:
                    shared.append(replace(layout, shared_from=grant.owner))
                    taken.add(layout.id)
        return own + shared

    async def list(
        self,
        workspace_id: str,
        *,
        seeds: Sequence[MapsLayout] = (),
        revisions: Mapping[str, int] | None = None,
    ) -> MapsLayoutList:
        policy = await self._access.policy(KIND_LAYOUT)
        allowed = [s for s in seeds if policy.allows(s.id, DEPLOYMENT, workspace_id)]
        if allowed:
            await self.ensure_seeded(workspace_id, allowed, revisions)
        settings = await self._settings.get(workspace_id)
        colors = dict(settings.layer_colors)
        layouts = [
            # A shared record takes this workspace's color when one was picked here.
            replace(layout, color=colors[layout.id])
            if layout.shared_from and layout.id in colors
            else layout
            for layout in await self._visible(workspace_id, policy)
        ]
        layouts.sort(key=lambda layout: (layout.order, layout.title.lower()))
        return MapsLayoutList(layouts=layouts, hidden=set(settings.hidden_layouts), colors=colors)

    async def visible(self, workspace_id: str) -> builtins.list[MapsLayout]:
        """Feeds the workspace may use: its own and those shared with it (no seeding)."""
        return await self._visible(workspace_id, await self._access.policy(KIND_LAYOUT))

    async def get(self, workspace_id: str, layout_id: str) -> MapsLayout:
        """A record the workspace may use: its own, or one shared with it."""
        policy = await self._access.policy(KIND_LAYOUT)
        for layout in await self._visible(workspace_id, policy):
            if layout.id == layout_id:
                return layout
        raise MapsLayoutNotFoundError(f"Map layout {layout_id!r} not found")

    async def _find(self, workspace_id: str, layout_id: str) -> MapsLayout | None:
        """The workspace's own record (shared ones are read-only here)."""
        try:
            layout = await self.get(workspace_id, layout_id)
        except MapsLayoutNotFoundError:
            return None
        if layout.shared_from:
            raise MapsLayoutPolicyError(
                f"Map layer {layout_id!r} is shared from another workspace: edit it there"
            )
        return layout

    async def save(
        self,
        workspace_id: str,
        layout: MapsLayout,
        *,
        user_id: str | None,
        reserved: set[str] | frozenset[str] = frozenset(),
    ) -> MapsLayout:
        existing = await self._find(workspace_id, layout.id)
        if existing is None and any(
            stored.id == layout.id and stored.system
            for stored in await self._store.list(workspace_id)
        ):
            # A deployment layer this workspace may not use any more: keep the id reserved.
            raise MapsLayoutValidationError([f"id {layout.id!r} is taken by a deployment layer"])
        # The system flag belongs to the seed, never to the request.
        layout = replace(layout, system=bool(existing and existing.system), shared_from="")
        if layout.feed_type == FEED_GEOJSON_URL:
            layout = replace(layout, query="", graphs=())
        errors = validate_layout(layout, reserved=reserved)
        if errors:
            raise MapsLayoutValidationError(errors)
        await self._store.save(workspace_id, layout, user_id=user_id)
        return layout

    async def delete(self, workspace_id: str, layout_id: str) -> None:
        existing = await self._find(workspace_id, layout_id)
        if existing is not None and existing.system:
            raise MapsLayoutPolicyError(
                f"Map layer {layout_id!r} is provided by the deployment: hide it instead"
            )
        if existing is None or not await self._store.delete(workspace_id, layout_id):
            raise MapsLayoutNotFoundError(f"Map layout {layout_id!r} not found")
        await self._access.forget(KIND_LAYOUT, layout_id, workspace_id)
        settings = await self._settings.get(workspace_id)
        if layout_id in settings.hidden_layouts or layout_id in settings.layer_colors:
            colors = {k: v for k, v in settings.layer_colors.items() if k != layout_id}
            await self._settings.save(
                workspace_id,
                settings.with_(
                    hidden_layouts=settings.hidden_layouts - {layout_id}, layer_colors=colors
                ),
                user_id=None,
            )

    async def set_hidden(
        self, workspace_id: str, layout_id: str, hidden: bool, *, user_id: str | None
    ) -> set[str]:
        if not LAYOUT_ID_PATTERN.match(layout_id):
            raise MapsLayoutValidationError(["invalid layout id"])
        settings = await self._settings.get(workspace_id)
        current = settings.hidden_layouts
        updated = current | {layout_id} if hidden else current - {layout_id}
        if updated != current:
            await self._settings.save(
                workspace_id, settings.with_(hidden_layouts=updated), user_id=user_id
            )
        return set(updated)

    async def set_color(
        self, workspace_id: str, layout_id: str, color: str | None, *, user_id: str | None
    ) -> dict[str, str]:
        """Default pin / cluster color of a layer.

        A stored layer keeps it on its record; built-in and graph layers (no
        record) keep it in the settings document. ``None`` resets the latter.
        """
        if not LAYOUT_ID_PATTERN.match(layout_id):
            raise MapsLayoutValidationError(["invalid layout id"])
        if color is not None and not COLOR_PATTERN.match(color):
            raise MapsLayoutValidationError(["color must be a #rrggbb hex value"])
        try:
            existing = await self._find(workspace_id, layout_id)
        except MapsLayoutPolicyError:
            existing = None  # shared record: this workspace keeps its own color
        settings = await self._settings.get(workspace_id)
        colors = {k: v for k, v in settings.layer_colors.items() if k != layout_id}
        if existing is not None:
            if color is None:
                raise MapsLayoutValidationError(["a stored layer needs a color"])
            await self._store.save(workspace_id, replace(existing, color=color), user_id=user_id)
        elif color is not None:
            colors[layout_id] = color
        if colors != settings.layer_colors:
            await self._settings.save(
                workspace_id, settings.with_(layer_colors=colors), user_id=user_id
            )
        return colors

    @staticmethod
    def validate(layout: MapsLayout) -> builtins.list[str]:
        return validate_layout(layout)

    async def feed(self, layout: MapsLayout, store: IGraphQueryStore) -> dict[str, Any]:
        if layout.feed_type != FEED_SPARQL:
            raise MapsLayoutValidationError(["only SPARQL layers run on the workspace graphs"])
        rows = await asyncio.to_thread(store.select, _with_limit(layout.query))
        pins = rows_to_pins(layout, rows)
        features = [pin_to_feature(pin) for pin in pins]
        return maps_feed_payload(features, source=layout.title)
