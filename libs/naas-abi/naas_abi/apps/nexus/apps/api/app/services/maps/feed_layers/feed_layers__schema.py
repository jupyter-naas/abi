"""Map layers: views on a feed (its features, or only some feature types).

A feed (``services/maps/layouts``: SPARQL or a Nexus API path) is the data
source; a layer is what the sidebar lists and the map draws: a title, icon,
color and order, plus ``class_labels`` — the feature types (pin ``classLabel``)
it keeps, or every feature when empty. A feed always has at least one layer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

LAYER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
ICON_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,47}$")
MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 500
MAX_CLASS_LABELS = 100
MAX_CLASS_LABEL_LENGTH = 80


@dataclass(frozen=True)
class MapsFeedLayer:
    id: str
    feed_id: str
    title: str
    color: str = "#2563eb"
    # Lucide key; empty = the feed's logo / icon.
    icon: str = ""
    description: str = ""
    order: int = 100
    # Feature types kept (pin classLabel); empty = every feature of the feed.
    class_labels: tuple[str, ...] = field(default_factory=tuple)
    # Seeded with a deployment feed: editable and hideable, never deleted.
    system: bool = False
    # Owning workspace when the feed is shared with this one (read-only here).
    shared_from: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["class_labels"] = list(self.class_labels)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapsFeedLayer:
        return cls(
            id=str(data["id"]),
            feed_id=str(data.get("feed_id", "")),
            title=str(data.get("title", "")),
            color=str(data.get("color", "#2563eb") or "#2563eb"),
            icon=str(data.get("icon", "") or ""),
            description=str(data.get("description", "") or ""),
            order=int(data.get("order", 100)),
            class_labels=tuple(str(v) for v in data.get("class_labels", []) or []),
            system=bool(data.get("system", False)),
            shared_from=str(data.get("shared_from", "") or ""),
        )


class MapsFeedLayerValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class MapsFeedLayerNotFoundError(LookupError):
    pass


class MapsFeedLayerPolicyError(PermissionError):
    """Refused by policy: seeded layer, a feed's last layer, a shared feed."""


def validate_feed_layer(
    layer: MapsFeedLayer, *, reserved: set[str] | frozenset[str] = frozenset()
) -> list[str]:
    errors: list[str] = []
    if not LAYER_ID_PATTERN.match(layer.id):
        errors.append("id must be lowercase letters, digits and dashes (max 48)")
    elif layer.id in reserved:
        errors.append(f"id {layer.id!r} is taken by a built-in layer")
    if not LAYER_ID_PATTERN.match(layer.feed_id):
        errors.append("feed_id must be a feed id")
    title = layer.title.strip()
    if not title:
        errors.append("title is required")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"title is too long (max {MAX_TITLE_LENGTH})")
    if len(layer.description) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"description is too long (max {MAX_DESCRIPTION_LENGTH})")
    if not COLOR_PATTERN.match(layer.color):
        errors.append("color must be a #rrggbb hex value")
    if layer.icon and not ICON_PATTERN.match(layer.icon):
        errors.append("icon must be an icon name")
    if len(layer.class_labels) > MAX_CLASS_LABELS:
        errors.append(f"at most {MAX_CLASS_LABELS} feature types per layer")
    elif any(not v.strip() or len(v) > MAX_CLASS_LABEL_LENGTH for v in layer.class_labels):
        errors.append(f"feature types must be 1-{MAX_CLASS_LABEL_LENGTH} characters")
    return errors
