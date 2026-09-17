"""MapsAgent tools for Nexus Maps.

Maps has no FastAPI domain: its layers are Next.js route handlers under
``apps/web/src/app/api/maps/<feed>/route.ts`` (CORS / User-Agent proxies for
public feeds) and the catalog is a TypeScript list in
``maps/lib/datasets.ts``. The agent therefore works from the source: this
tool parses that catalog so "which layers exist?" has a real answer, and the
Nexus source tools cover the rest. The layer open on ``/maps/<datasetId>``
arrives as the open feature resource (kind ``map_dataset``).
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.tools.nexus_source_tools import PACKAGE_ROOT

MAP_DATASET_RESOURCE_KIND = "map_dataset"
_WEB = PACKAGE_ROOT / "apps/nexus/apps/web/src"
CATALOG_PATH = _WEB / "app/workspace/[workspaceId]/maps/lib/datasets.ts"
FEEDS_DIR = _WEB / "app/api/maps"
_FIELD_RE = {
    key: re.compile(rf"\b{key}:\s*(?:'((?:[^'\\]|\\.)*)'|\n\s*'((?:[^'\\]|\\.)*)')")
    for key in ("id", "title", "description", "category")
}
_ENTRY_SPLIT_RE = re.compile(r"\n\s*\{\s*\n")


def parse_maps_catalog(text: str) -> list[dict[str, str]]:
    """Built-in dataset entries (id, title, description, category)."""
    start = text.find("MAPS_BUILTIN_DATASETS")
    if start < 0:
        return []
    body = text[start : text.find("];", start)]
    entries: list[dict[str, str]] = []
    for chunk in _ENTRY_SPLIT_RE.split(body)[1:]:
        entry: dict[str, str] = {}
        for key, pattern in _FIELD_RE.items():
            match = pattern.search(chunk)
            if match:
                entry[key] = (match.group(1) or match.group(2) or "").replace(
                    "\\'", "'"
                )
        if entry.get("id"):
            entries.append(entry)
    return entries


def maps_tools() -> list[BaseTool]:
    @tool
    def list_map_layers() -> Any:
        """List the built-in Maps layers (id, title, description, category) and
        which ones have a server feed route under /api/maps/. Also names the
        layer open in the page, if any."""
        if not CATALOG_PATH.is_file():
            return {
                "error": (
                    "The Nexus web sources are not shipped in this deployment, so "
                    "the Maps catalog cannot be read here."
                )
            }
        layers = parse_maps_catalog(CATALOG_PATH.read_text(encoding="utf-8"))
        feeds = sorted(
            p.name for p in FEEDS_DIR.iterdir() if (p / "route.ts").is_file()
        )
        for layer in layers:
            layer["feed_route"] = (
                f"/api/maps/{layer['id']}" if layer["id"] in feeds else ""
            )
        return {
            "catalog": "naas_abi/apps/nexus/apps/web/src/app/workspace/[workspaceId]/maps/lib/datasets.ts",
            "open_layer": active_feature_resource_id(MAP_DATASET_RESOURCE_KIND),
            "layers": layers,
            "feed_routes": feeds,
            "custom_layers": "Registered per deployment via NEXT_PUBLIC_MAPS_CUSTOM_DATASETS.",
        }

    return [list_map_layers]
