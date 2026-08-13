"""Canonical filesystem paths for the Personnel Cockpit app."""

from __future__ import annotations

from pathlib import Path

COCKPIT_ROOT = Path(__file__).resolve().parent
PERSONNEL_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = COCKPIT_ROOT / "web"
WEB_DATA = WEB_ROOT / "data"
ENTITY_DEMO = WEB_DATA / "entities" / "_demo"
GRAPH_FILE = PERSONNEL_ROOT / "data" / "graph" / "personnel_demo.ttl"
