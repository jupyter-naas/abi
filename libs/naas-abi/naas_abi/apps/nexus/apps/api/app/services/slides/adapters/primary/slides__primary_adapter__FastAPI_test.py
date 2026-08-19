"""Unit tests for Slides helpers (no live Forgejo)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary.slides__primary_adapter__FastAPI import (
    _assets_dir,
    _assets_gitkeep_path,
    _branch_for,
    _coder_workspace_name,
    _deck_path,
    _discover_seed_ids,
    _friendly_coding_detail,
    _friendly_git_detail,
    _is_git_write_race,
    _legacy_branch_for,
    _legacy_deck_path,
    _list_seed_template_records,
    _load_seed_html,
    _paths_for,
    _probe_sidecar,
    _project_path,
    _read_deck_via_sidecar,
    _runtime_label,
    _sidecar_tool_call,
    _slugify,
    _wait_for_sidecar,
    _write_deck_via_sidecar,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    WorkspaceNameConflictError,
)


def test_slugify_and_paths() -> None:
    assert _slugify("Q3 Business Review!") == "q3-business-review"
    assert _branch_for("ws-abc", "demo") == "slides/ws-abc/demo"
    assert _deck_path("ws-abc", "demo") == "slides/ws-abc/demo/deck.html"
    assert _project_path("ws-abc", "demo") == "slides/ws-abc/demo/project.json"
    assert _assets_dir("ws-abc", "demo") == "slides/ws-abc/demo/assets"
    assert _assets_gitkeep_path("ws-abc", "demo") == "slides/ws-abc/demo/assets/.gitkeep"
    assert _runtime_label("ws-abc", "q3-br") == "slides/ws-abc/q3-br"
    assert _coder_workspace_name("ws-abc", "q3-br").startswith("s-")
    assert _legacy_branch_for("demo") == "slides/demo"
    assert _legacy_deck_path("demo") == "slides/demo/deck.html"
    ns = _paths_for("ws-abc", "demo", legacy=False)
    assert ns["branch"] == "slides/ws-abc/demo"
    legacy = _paths_for("ws-abc", "demo", legacy=True)
    assert legacy["branch"] == "slides/demo"


def test_seed_template_includes_build_pptx() -> None:
    html = _load_seed_html("minimal-light-v1")
    assert "function buildPptx" in html
    assert "PptxGenJS" in html or "pptxgen" in html.lower()
    assert "data:image/" in html


def test_seed_catalog_lists_all_templates() -> None:
    ids = _discover_seed_ids()
    assert "pitch-dark-v1" in ids
    assert "minimal-light-v1" in ids
    assert "executive-v1" in ids
    assert len(ids) == 3
    assert ids[0] == "minimal-light-v1"
    records = _list_seed_template_records()
    by_id = {r["id"]: r for r in records}
    assert by_id["minimal-light-v1"]["name"] == "Minimal Light"
    assert by_id["pitch-dark-v1"]["preview_bg"].startswith("#")
    for tid in ("pitch-dark-v1", "minimal-light-v1", "executive-v1"):
        html = _load_seed_html(tid)
        assert "function buildPptx" in html
        assert 'class="deck"' in html
        assert 'class="slide' in html
        assert "deck-menubar" in html


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


def test_friendly_git_detail_hides_pushrejected_dump() -> None:
    raw = (
        "Forgejo API request failed (500): PushRejected ... "
        "cannot lock ref 'refs/heads/slides/demo-deck': "
        "is at 4c232bab... but expected e621205..."
    )
    assert _is_git_write_race(raw) is True
    assert _friendly_git_detail(Exception(raw)) == (
        "Git write raced on the deck branch; retrying is safe"
    )
    assert _friendly_coding_detail(Exception(raw)) == (
        "Git write raced on the deck branch; retrying is safe"
    )
    assert "Coder runtime" not in _friendly_coding_detail(Exception(raw))


def test_probe_sidecar_requires_base_and_secret() -> None:
    assert _probe_sidecar(None, "secret") is False
    assert _probe_sidecar("http://coder-x-slides-demo:8378", None) is False
    assert _probe_sidecar("", "") is False


def test_wait_for_sidecar_retries_until_ready(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_probe(base, secret, *, timeout_s=2.0):  # noqa: ANN001
        calls["n"] += 1
        return calls["n"] >= 3

    sleeps: list[float] = []
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary."
        "slides__primary_adapter__FastAPI._probe_sidecar",
        fake_probe,
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary."
        "slides__primary_adapter__FastAPI.time.sleep",
        sleeps.append,
    )
    assert (
        _wait_for_sidecar(
            "http://coder-x-slides-demo:8378", "secret", attempts=5, interval_s=0.01
        )
        is True
    )
    assert calls["n"] == 3
    assert len(sleeps) == 2


def test_wait_for_sidecar_gives_up(monkeypatch) -> None:
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary."
        "slides__primary_adapter__FastAPI._probe_sidecar",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary."
        "slides__primary_adapter__FastAPI.time.sleep",
        lambda *_: None,
    )
    assert (
        _wait_for_sidecar(
            "http://coder-x-slides-demo:8378", "secret", attempts=3, interval_s=0.01
        )
        is False
    )


def test_sidecar_tool_helpers_require_binding() -> None:
    assert _sidecar_tool_call(None, "s", "read_file", {"path": "x"}) == {
        "error": "sidecar not bound"
    }
    assert _read_deck_via_sidecar(None, "s", deck_path="slides/ws/demo/deck.html") is None
    assert (
        _write_deck_via_sidecar(
            None, "s", deck_path="slides/ws/demo/deck.html", html="<html></html>"
        )
        is False
    )
    assert (
        _sidecar_tool_call("file:///tmp", "s", "read_file", {"path": "x"}).get("error")
        or ""
    ).startswith("invalid sidecar base url")
