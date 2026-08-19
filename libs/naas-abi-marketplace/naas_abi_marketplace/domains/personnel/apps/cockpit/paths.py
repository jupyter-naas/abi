"""Canonical filesystem paths for the Personnel Cockpit app."""

from __future__ import annotations

from pathlib import Path

from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    load_default_entity,
)

COCKPIT_ROOT = Path(__file__).resolve().parent
PERSONNEL_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENTITY = load_default_entity()
DEFAULT_ENTITY_ID = _DEFAULT_ENTITY["entity_id"]
DEFAULT_ENTITY_SLUG = _DEFAULT_ENTITY["url_slug"]
WEB_ROOT = COCKPIT_ROOT / "web"
DATA_ROOT = COCKPIT_ROOT / "data"
ENTITY_DATA = DATA_ROOT / "entities" / DEFAULT_ENTITY_ID
GRAPH_FILE = PERSONNEL_ROOT / "data" / "graph" / "personnel_demo.ttl"


def entity_dir(entity_id: str) -> Path:
    return DATA_ROOT / "entities" / entity_id
