"""Resolve personnel cockpit datasets with ObjectStorage → TripleStore → data fallback.

Committed app datasets live under ``apps/cockpit/data/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from naas_abi_core import logger

from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import (
    DATA_ROOT,
    ENTITY_DATA,
    GRAPH_FILE,
)

# ObjectStorage key prefix under the personnel module datastore_path.
STORAGE_APPS_PREFIX = "apps/cockpit"


def cockpit_web_data() -> Path:
    return DATA_ROOT


def demo_graph_path() -> Path:
    return GRAPH_FILE


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def entity_manifest_path() -> Path:
    return ENTITY_DATA / "manifest.json"


def list_page_files(page_id: str) -> list[Path]:
    """Return dataset paths for a cockpit page from the committed data tree."""
    manifest_path = entity_manifest_path()
    if not manifest_path.exists():
        return []
    manifest = load_json(manifest_path)
    rels = manifest.get("datasets", {}).get("pages", {}).get(page_id, [])
    return [ENTITY_DATA / rel for rel in rels if (ENTITY_DATA / rel).exists()]


def load_page(page_id: str) -> dict[str, Any]:
    """Load all datasets for a page keyed by basename (without .json)."""
    out: dict[str, Any] = {}
    for path in list_page_files(page_id):
        out[path.stem] = load_json(path)
    return out


def _storage_has_prefix(object_storage: Any, prefix: str) -> bool:
    """Return True if ObjectStorage already has at least one object under *prefix*."""
    list_fn = getattr(object_storage, "list_objects", None) or getattr(
        object_storage, "list", None
    )
    if list_fn is None:
        return False
    try:
        items = list_fn(prefix)
        return bool(items)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"demo_fallback: ObjectStorage list failed ({exc})")
        return False


def _triplestore_has_personnel(triple_store: Any, graph_name: str) -> bool:
    """ASK whether the personnel named graph has any triple."""
    sparql = f"ASK {{ GRAPH <{graph_name}> {{ ?s ?p ?o }} }}"
    try:
        return bool(triple_store.query(sparql).askAnswer)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"demo_fallback: TripleStore ASK failed ({exc})")
        return False


def resolve_apps_data_root(
    *,
    object_storage: Any | None = None,
    triple_store: Any | None = None,
    graph_name: str = "http://ontology.naas.ai/graph/personnel",
    datastore_path: str = "personnel",
) -> tuple[str, Path]:
    """Pick the dataset root to serve.

    Returns ``(source, path)`` where *source* is one of
    ``object_storage`` | ``triple_store`` | ``web_data``.

    - If ObjectStorage has keys under ``{datastore}/apps/cockpit/``,
      callers should read from storage (path is the logical prefix).
    - Else if the TripleStore personnel graph is non-empty, callers should
      SPARQL live (path still points at data for shape reference).
    - Else fall back to committed ``apps/cockpit/data``.
    """
    storage_prefix = f"{datastore_path.rstrip('/')}/{STORAGE_APPS_PREFIX}"

    if object_storage is not None and _storage_has_prefix(
        object_storage, storage_prefix
    ):
        return "object_storage", Path(storage_prefix)

    if triple_store is not None and _triplestore_has_personnel(
        triple_store, graph_name
    ):
        return "triple_store", DATA_ROOT

    if not ENTITY_DATA.exists():
        raise FileNotFoundError(
            f"Cockpit datasets missing at {ENTITY_DATA}. "
            "Run: cd domains/personnel && make demo"
        )

    logger.info(
        "personnel data: using apps/cockpit/data "
        "(ObjectStorage empty and TripleStore graph empty or unavailable)"
    )
    return "web_data", DATA_ROOT
