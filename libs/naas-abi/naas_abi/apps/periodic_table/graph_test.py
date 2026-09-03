"""Tests for the ABI Periodic Table visualization app."""

from __future__ import annotations

import json
from pathlib import Path

from naas_abi.ontologies.periodic_table.loader import extract_elements

APP_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = APP_DIR / "manifest.json"


def test_manifest_registers_bundled_html() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["name"] == "Periodic Table of Software"
    assert manifest["url"] == "html:periodic_table_graph.html"
    assert manifest["category"] == "core"


def test_manifest_url_resolves_to_app_html() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (
        _resolve_manifest_url,
    )

    resolved = _resolve_manifest_url(
        "html:periodic_table_graph.html", "naas_abi", "periodic_table"
    )
    assert resolved == "/app-html/naas_abi/periodic_table/periodic_table_graph.html"


def test_app_uses_abi_ontology() -> None:
    elements = extract_elements()
    assert len(elements) == 119
    assert {e.local_name for e in elements} >= {
        "DocInterface",
        "SheetInterface",
        "SlideInterface",
        "Portal",
    }


def test_bundled_html_exists() -> None:
    html = APP_DIR / "periodic_table_graph.html"
    assert html.is_file()
    text = html.read_text(encoding="utf-8")
    assert len(text) > 1000
    assert "Periodic Table" in text or "network" in text.lower()
