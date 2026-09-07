"""Resolve the personnel cockpit dataset source (ObjectStorage → TripleStore).

Runtime datasets live in ObjectStorage under ``personnel/apps/cockpit/data/``.
The committed ``apps/cockpit/data/`` tree is a structure reference only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.domains.personnel.apps.cockpit.data_store import (
    read_json as read_storage_json,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.data_store import (
    storage_has_datasets,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import DATA_ROOT
from naas_abi_marketplace.domains.personnel.paths import (
    cockpit_storage_prefix,
    module_datastore_path,
    module_graph_name,
)


def demo_graph_path() -> Path:
    from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE

    return DEMO_GRAPH_FILE


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _storage_has_prefix(object_storage: Any, prefix: str) -> bool:
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
    graph_name: str | None = None,
    datastore_path: str | None = None,
) -> tuple[str, Path]:
    """Pick the dataset source for the cockpit app.

    Returns ``(source, path)`` where *source* is one of
    ``object_storage`` | ``triple_store``.

    Cockpit JSON is always read from ObjectStorage when available.
    """
    resolved_datastore = datastore_path or module_datastore_path()
    storage_prefix = cockpit_storage_prefix(resolved_datastore)
    resolved_graph = graph_name or module_graph_name()

    if storage_has_datasets(datastore_path=resolved_datastore):
        return "object_storage", Path(storage_prefix)

    if object_storage is not None and _storage_has_prefix(object_storage, storage_prefix):
        return "object_storage", Path(storage_prefix)

    if triple_store is not None and _triplestore_has_personnel(triple_store, resolved_graph):
        logger.info(
            "personnel data: TripleStore graph populated; "
            "cockpit still expects ObjectStorage datasets — run make demo-data"
        )
        return "triple_store", DATA_ROOT

    raise FileNotFoundError(
        f"Cockpit datasets missing in ObjectStorage at {storage_prefix}/. "
        "Run: cd domains/personnel && make demo-data"
    )


def load_page_from_storage(page_id: str, *, entity_id: str) -> dict[str, Any]:
    manifest = read_storage_json(f"entities/{entity_id}/manifest.json")
    rels = manifest.get("datasets", {}).get("pages", {}).get(page_id, [])
    out: dict[str, Any] = {}
    for rel in rels:
        stem = Path(rel).stem
        out[stem] = read_storage_json(f"entities/{entity_id}/{rel}")
    return out
