"""Unit tests for Slides helpers (no live Forgejo)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary.slides__primary_adapter__FastAPI import (
    _branch_for,
    _deck_path,
    _load_seed_html,
    _project_path,
    _slugify,
)


def test_slugify_and_paths() -> None:
    assert _slugify("Q3 Business Review!") == "q3-business-review"
    assert _branch_for("demo") == "slides/demo"
    assert _deck_path("demo") == "slides/demo/deck.html"
    assert _project_path("demo") == "slides/demo/project.json"


def test_seed_template_includes_build_pptx() -> None:
    html = _load_seed_html("bob-fmz-v1")
    assert "function buildPptx" in html
    assert "PptxGenJS" in html or "pptxgen" in html.lower()
