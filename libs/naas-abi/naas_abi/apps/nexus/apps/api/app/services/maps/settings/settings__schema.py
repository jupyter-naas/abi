"""A workspace's Maps settings: what is hidden, layer colors, which seeds were applied."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any


def _ids(value: Any) -> frozenset[str]:
    return frozenset(str(v) for v in value or [] if isinstance(v, str) and v)


@dataclass(frozen=True)
class MapsWorkspaceSettings:
    """One JSON document per workspace (``maps_settings.settings``).

    ``seeded_*`` remember which deployment seeds were already copied into the
    workspace, so a record an admin deleted is not re-created on the next list.
    """

    hidden_layouts: frozenset[str] = frozenset()
    hidden_basemaps: frozenset[str] = frozenset()
    layer_colors: dict[str, str] = field(default_factory=dict)
    seeded_layouts: frozenset[str] = frozenset()
    seeded_basemaps: frozenset[str] = frozenset()
    # Revision applied per seed ("layout:<id>", "layer:<id>"); a higher seed
    # revision re-applies the seed to its system record (deployment migration).
    seed_revisions: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "hidden_layouts": sorted(self.hidden_layouts),
                "hidden_basemaps": sorted(self.hidden_basemaps),
                "layer_colors": dict(sorted(self.layer_colors.items())),
                "seeded_layouts": sorted(self.seeded_layouts),
                "seeded_basemaps": sorted(self.seeded_basemaps),
                "seed_revisions": dict(sorted(self.seed_revisions.items())),
            }
        )

    @classmethod
    def from_json(cls, raw: str | None) -> MapsWorkspaceSettings:
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        colors = data.get("layer_colors")
        revisions = data.get("seed_revisions")
        return cls(
            hidden_layouts=_ids(data.get("hidden_layouts")),
            hidden_basemaps=_ids(data.get("hidden_basemaps")),
            layer_colors=(
                {str(k): str(v) for k, v in colors.items()} if isinstance(colors, dict) else {}
            ),
            seeded_layouts=_ids(data.get("seeded_layouts")),
            seeded_basemaps=_ids(data.get("seeded_basemaps")),
            seed_revisions=(
                {str(k): int(v) for k, v in revisions.items() if isinstance(v, int)}
                if isinstance(revisions, dict)
                else {}
            ),
        )

    def with_(self, **changes: Any) -> MapsWorkspaceSettings:
        return replace(self, **changes)


def applied_revision(settings: MapsWorkspaceSettings, kind: str, item_id: str) -> int:
    """Seed revision already applied in the workspace (feeds seeded before revisions: 1)."""
    key = f"{kind}:{item_id}"
    if key in settings.seed_revisions:
        return settings.seed_revisions[key]
    return 1 if kind == "layout" and item_id in settings.seeded_layouts else 0
