"""Workspace map layouts: SPARQL-defined pin layers plus which layouts are hidden."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

LAYOUT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_QUERY_LENGTH = 20_000
MAX_PINS = 2_000

# Built-in layouts drawn by the web app (web/src/app/workspace/[workspaceId]/maps/lib/datasets.ts).
# A custom layout cannot take one of these ids; any of them can be hidden.
# ``all`` is the route of the combined map.
BUILTIN_LAYOUT_IDS = frozenset(
    {
        "openstreetmap",
        "earthquakes",
        "wildfires",
        "temperature",
        "natural-earth",
        "gdacs",
        "eonet-all",
        "openaq",
        "nws-alerts",
        "tropical-storms",
        "volcanoes",
        "flights",
        "conflict",
        "gulf-strikes",
        "news",
        "ais",
        "iss",
        "presence",
        "all",  # the combined "All layouts" map's route
    }
)

# What a layout query must / may project. ?uri links a pin to its record,
# ?graph to the graph it came from; ?detail is the line under the label.
REQUIRED_VARIABLES = frozenset({"label", "lat", "lng"})
OPTIONAL_VARIABLES = frozenset({"uri", "graph", "detail"})


@dataclass(frozen=True)
class MapsLayout:
    """A custom layout: pins from a SELECT over the workspace's graphs."""

    id: str
    title: str
    query: str
    description: str = ""
    icon: str = "MapPin"
    color: str = "#2563eb"
    graphs: tuple[str, ...] = field(default_factory=tuple)
    order: int = 100

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["graphs"] = list(self.graphs)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapsLayout:
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            query=str(data.get("query", "")),
            description=str(data.get("description", "")),
            icon=str(data.get("icon", "MapPin")),
            color=str(data.get("color", "#2563eb")),
            graphs=tuple(str(g) for g in data.get("graphs", []) or []),
            order=int(data.get("order", 100)),
        )


@dataclass(frozen=True)
class MapsLayoutList:
    layouts: list[MapsLayout]
    hidden: set[str]


class MapsLayoutValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class MapsLayoutNotFoundError(LookupError):
    pass
