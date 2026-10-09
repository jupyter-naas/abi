"""Workspace Maps layouts: custom SPARQL pin layers and per-workspace visibility.

A layout's query runs through the workspace-scoped graph store, so it reads
only what the workspace may read. Queries are validated on save: SELECT only,
no SERVICE / FROM (the dataset is the workspace's), and ?label ?lat ?lng
projected.
"""

from __future__ import annotations

import asyncio
import math
import re
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
    query_shape,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    COLOR_PATTERN,
    LAYOUT_ID_PATTERN,
    MAX_PINS,
    MAX_QUERY_LENGTH,
    REQUIRED_VARIABLES,
    MapsLayout,
    MapsLayoutList,
    MapsLayoutNotFoundError,
    MapsLayoutValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.port import MapsLayoutStorePort
from rdflib.plugins.sparql import prepareQuery

_LIMIT_AT_END = re.compile(r"\bLIMIT\s+\d+\s*(OFFSET\s+\d+\s*)?$", re.IGNORECASE)


def _projected(sparql: str) -> set[str]:
    return {str(v) for v in prepareQuery(sparql).algebra.get("PV") or []}


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
    def __init__(self, store: MapsLayoutStorePort) -> None:
        self._store = store

    async def list(self, workspace_id: str) -> MapsLayoutList:
        layouts = sorted(
            await self._store.list(workspace_id),
            key=lambda layout: (layout.order, layout.title.lower()),
        )
        return MapsLayoutList(layouts=layouts, hidden=await self._store.get_hidden(workspace_id))

    async def get(self, workspace_id: str, layout_id: str) -> MapsLayout:
        for layout in await self._store.list(workspace_id):
            if layout.id == layout_id:
                return layout
        raise MapsLayoutNotFoundError(f"Map layout {layout_id!r} not found")

    async def save(
        self,
        workspace_id: str,
        layout: MapsLayout,
        *,
        user_id: str | None,
        reserved: set[str] | frozenset[str] = frozenset(),
    ) -> MapsLayout:
        errors = validate_layout(layout, reserved=reserved)
        if errors:
            raise MapsLayoutValidationError(errors)
        await self._store.save(workspace_id, layout, user_id=user_id)
        return layout

    async def delete(self, workspace_id: str, layout_id: str) -> None:
        if not await self._store.delete(workspace_id, layout_id):
            raise MapsLayoutNotFoundError(f"Map layout {layout_id!r} not found")
        hidden = await self._store.get_hidden(workspace_id)
        if layout_id in hidden:
            await self._store.set_hidden(workspace_id, hidden - {layout_id}, user_id=None)

    async def set_hidden(
        self, workspace_id: str, layout_id: str, hidden: bool, *, user_id: str | None
    ) -> set[str]:
        if not LAYOUT_ID_PATTERN.match(layout_id):
            raise MapsLayoutValidationError(["invalid layout id"])
        current = await self._store.get_hidden(workspace_id)
        updated = current | {layout_id} if hidden else current - {layout_id}
        if updated != current:
            await self._store.set_hidden(workspace_id, updated, user_id=user_id)
        return updated

    @staticmethod
    def validate(layout: MapsLayout) -> list[str]:
        return validate_layout(layout)

    async def feed(self, layout: MapsLayout, store: IGraphQueryStore) -> dict[str, Any]:
        rows = await asyncio.to_thread(store.select, _with_limit(layout.query))
        pins = rows_to_pins(layout, rows)
        return {"pins": pins, "count": len(pins), "source": layout.title}
