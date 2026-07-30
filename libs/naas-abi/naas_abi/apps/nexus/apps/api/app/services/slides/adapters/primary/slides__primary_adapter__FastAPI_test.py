"""Unit tests for Slides helpers (no live Forgejo)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary.slides__primary_adapter__FastAPI import (
    _assets_dir,
    _assets_gitkeep_path,
    _branch_for,
    _coder_workspace_name,
    _count_embedded_images,
    _deck_path,
    _friendly_coding_detail,
    _load_seed_html,
    _probe_sidecar,
    _project_path,
    _runtime_label,
    _slugify,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    WorkspaceNameConflictError,
)


def test_slugify_and_paths() -> None:
    assert _slugify("Q3 Business Review!") == "q3-business-review"
    assert _branch_for("demo") == "slides/demo"
    assert _deck_path("demo") == "slides/demo/deck.html"
    assert _project_path("demo") == "slides/demo/project.json"
    assert _assets_dir("demo") == "slides/demo/assets"
    assert _assets_gitkeep_path("demo") == "slides/demo/assets/.gitkeep"
    assert _runtime_label("q3-br") == "slides/q3-br"
    assert _coder_workspace_name("q3-br") == "slides-q3-br"


def test_seed_template_includes_build_pptx() -> None:
    html = _load_seed_html("bob-fmz-v1")
    assert "function buildPptx" in html
    assert "PptxGenJS" in html or "pptxgen" in html.lower()
    assert _count_embedded_images(html) >= 1


def test_friendly_coding_detail_hides_raw_coder_json() -> None:
    raw = (
        '{"message":"Workspace \\"slides-q3-br\\" already exists.",'
        '"validations":[{"field":"name","detail":"This value is already in use '
        'and should be unique."}]}'
    )
    assert _friendly_coding_detail(WorkspaceNameConflictError(raw)) == (
        "Reconnecting to existing runtime…"
    )
    assert _friendly_coding_detail(Exception(raw)) == (
        "Reconnecting to existing runtime…"
    )


def test_probe_sidecar_requires_base_and_secret() -> None:
    assert _probe_sidecar(None, "secret") is False
    assert _probe_sidecar("http://coder-x-slides-demo:8378", None) is False
    assert _probe_sidecar("", "") is False
