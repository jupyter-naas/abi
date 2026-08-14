"""Canonical filesystem paths for the Personnel Cockpit app."""

from __future__ import annotations

from pathlib import Path

COCKPIT_ROOT = Path(__file__).resolve().parent
PERSONNEL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENTITY_ID = "demo"
DEFAULT_ENTITY_SLUG = "demo"
WEB_ROOT = COCKPIT_ROOT / "web"
DATA_ROOT = COCKPIT_ROOT / "data"
ENTITY_DATA = DATA_ROOT / "entities" / DEFAULT_ENTITY_ID
GRAPH_FILE = PERSONNEL_ROOT / "data" / "graph" / "personnel_demo.ttl"


def entity_dir(entity_id: str) -> Path:
    return DATA_ROOT / "entities" / entity_id
