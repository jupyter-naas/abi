"""Unit tests for Slides helpers (no live Forgejo)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary.slides__primary_adapter__FastAPI import (
    TreeEntryResponse,
    _assets_dir,
    _assets_gitkeep_path,
    _branch_for,
    _coder_workspace_name,
    _curate_project_tree,
    _deck_path,
    _discover_seed_ids,
    _ensure_coding_repo,
    _friendly_coding_detail,
    _friendly_git_detail,
    _is_git_write_race,
    _legacy_branch_for,
    _legacy_deck_path,
    _list_seed_template_records,
    _load_seed_html,
    _parse_slide_outline,
    _parse_template_assets,
    _paths_for,
    _probe_sidecar,
    _project_path,
    _read_deck_via_sidecar,
    _repo_id,
    _runtime_label,
    _sidecar_tool_call,
    _slugify,
    _source_control_http_error,
    _validate_asset_name,
    _wait_for_sidecar,
    _write_deck_via_sidecar,
)
from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary import (
    slides__primary_adapter__FastAPI as slides_api,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    WorkspaceNameConflictError,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import RepoNotFoundError
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
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


def test_parse_slide_outline_reads_eyebrow_and_h1() -> None:
    html = """
    <main class="deck">
      <section id="slide-cover" class="slide cover">
        <div class="eyebrow">Confidential</div>
        <h1>Presentation Title</h1>
      </section>
      <section class="slide section-divider">
        <div class="divider-eyebrow">Section 01</div>
        <div class="divider-title">Context</div>
      </section>
    </main>
    """
    slides = _parse_slide_outline(html)
    assert len(slides) == 2
    assert slides[0]["id"] == "slide-cover"
    assert slides[0]["eyebrow"] == "Confidential"
    assert slides[0]["title"] == "Presentation Title"
    assert slides[1]["eyebrow"] == "Section 01"
    assert slides[1]["title"] == "Context"
    assets = _parse_template_assets(
        'const IMG = {\n  hero: "data:image/svg+xml,x",\n  logo: "data:image/svg+xml,y",\n};'
    )
    assert [a["name"] for a in assets] == ["hero", "logo"]


def test_seed_template_includes_build_pptx() -> None:
    html = _load_seed_html("minimal-light-v1")
    assert "function buildPptx" in html
    assert "PptxGenJS" in html or "pptxgen" in html.lower()
    assert "data:image/" in html
    assert "NEXUS_SLIDES_PPTX_FROM_DOM_V1" in html
    assert 'querySelectorAll("main.deck > section.slide' in html
    assert '[["1","Context"],["2","Approach"]' not in html


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
    light_slides = by_id["minimal-light-v1"]["slides"]
    titles = [s["title"] for s in light_slides]
    assert "Presentation Title" in titles
    assert "What we will cover" in titles
    assert any(s.get("eyebrow") == "Agenda" for s in light_slides)
    assert by_id["minimal-light-v1"]["assets"]
    for tid in ("pitch-dark-v1", "minimal-light-v1", "executive-v1"):
        html = _load_seed_html(tid)
        assert "function buildPptx" in html
        assert "NEXUS_SLIDES_PPTX_FROM_DOM_V1" in html
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


def test_friendly_git_detail_rewrites_raw_repo_id() -> None:
    err = RepoNotFoundError("abi/monorepo")
    detail = _friendly_git_detail(err)
    assert "abi/monorepo" in detail
    assert "missing" in detail.lower()
    http = _source_control_http_error(err)
    assert http.status_code == 503
    assert "Forgejo is not configured" in str(http.detail)


def test_source_control_http_error_unreachable() -> None:
    http = _source_control_http_error(OSError("Connection refused"))
    assert http.status_code == 503
    assert "not reachable" in str(http.detail).lower()


def test_ensure_coding_repo_seeds_empty_in_memory() -> None:
    sc = SourceControlService(InMemoryAdapter())
    repo_id = _repo_id()
    assert repo_id.count("/") == 1
    try:
        sc.list_branches(repo_id=repo_id)
        raise AssertionError("empty in_memory should not have the coding repo")
    except RepoNotFoundError:
        pass
    assert _ensure_coding_repo(sc) == repo_id
    assert [b.name for b in sc.list_branches(repo_id=repo_id)]


def _slides_client(monkeypatch, source_control: SourceControlService) -> TestClient:
    app = FastAPI()
    app.state.source_control = source_control
    app.include_router(slides_api.router, prefix="/slides")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="admin@example.com", name="Zen Admin"
    )

    async def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db

    async def _allow(user_id: str, workspace_id: str) -> str:
        return "owner"

    monkeypatch.setattr(slides_api, "require_workspace_access", _allow)
    monkeypatch.setattr(slides_api, "_get_coding_environment", lambda _request: None)
    return TestClient(app)


def test_list_and_create_projects_seed_in_memory_repo(monkeypatch) -> None:
    sc = SourceControlService(InMemoryAdapter())
    client = _slides_client(monkeypatch, sc)
    listed = client.get("/slides/projects", params={"workspace_id": "ws-test"})
    assert listed.status_code == 200, listed.text
    assert listed.json() == []
    created = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "Untitled presentation",
            "slug": "untitled-local",
            "template_id": "minimal-light-v1",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["slug"] == "untitled-local"
    assert body["deck_path"] == "slides/ws-test/untitled-local/deck.html"
    listed2 = client.get("/slides/projects", params={"workspace_id": "ws-test"})
    assert listed2.status_code == 200, listed2.text
    assert "untitled-local" in [p["slug"] for p in listed2.json()]
    templates = client.get("/slides/templates", params={"workspace_id": "ws-test"})
    assert templates.status_code == 200, templates.text
    catalog = templates.json()
    assert {t["id"] for t in catalog} >= {
        "minimal-light-v1",
        "pitch-dark-v1",
        "executive-v1",
    }
    light = next(t for t in catalog if t["id"] == "minimal-light-v1")
    assert light["name"] == "Minimal Light"
    assert any(s["title"] == "What we will cover" for s in light["slides"])
    applied = client.post(
        "/slides/projects/untitled-local/apply-template",
        json={"workspace_id": "ws-test", "template_id": "pitch-dark-v1"},
    )
    assert applied.status_code == 200, applied.text
    deck = client.get(
        "/slides/projects/untitled-local/deck",
        params={"workspace_id": "ws-test"},
    )
    assert deck.status_code == 200, deck.text
    html = deck.json()["html"]
    assert 'content="pitch-dark-v1"' in html
    proj = client.get(
        "/slides/projects/untitled-local",
        params={"workspace_id": "ws-test"},
    )
    assert proj.status_code == 200, proj.text
    assert proj.json()["template_id"] == "pitch-dark-v1"


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


def test_curate_project_tree_hides_inmemory_dump() -> None:
    root = "slides/ws-test/untitled-local"
    junk = [
        TreeEntryResponse(name="README.md", path="README.md", type="file"),
        TreeEntryResponse(
            name="slides/ws-test/untitled-local/deck.html",
            path="slides/ws-test/untitled-local/deck.html",
            type="file",
        ),
        TreeEntryResponse(
            name="slides/ws-test/untitled-local/project.json",
            path="slides/ws-test/untitled-local/project.json",
            type="file",
        ),
        TreeEntryResponse(
            name="slides/ws-test/untitled-local/assets/.gitkeep",
            path="slides/ws-test/untitled-local/assets/.gitkeep",
            type="file",
        ),
        TreeEntryResponse(
            name="slides/ws-test/untitled-local/assets/README.md",
            path="slides/ws-test/untitled-local/assets/README.md",
            type="file",
        ),
        TreeEntryResponse(
            name="slides/ws-test/untitled-local/assets/hero.svg",
            path="slides/ws-test/untitled-local/assets/hero.svg",
            type="file",
            size=12,
        ),
        TreeEntryResponse(
            name="slides/ws-other/other-deck/deck.html",
            path="slides/ws-other/other-deck/deck.html",
            type="file",
        ),
        TreeEntryResponse(
            name="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            path="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            type="dir",
        ),
        TreeEntryResponse(name=".coder", path=".coder", type="dir"),
    ]
    entries, assets = _curate_project_tree(
        junk,
        root=root,
        deck_path=f"{root}/deck.html",
        project_path=f"{root}/project.json",
        assets_dir=f"{root}/assets",
    )
    names = [e.name for e in entries]
    assert names == ["assets", "deck.html", "project.json"]
    assert all("/" not in e.name for e in entries)
    assert [a.name for a in assets] == ["hero.svg"]
    assert assets[0].path == f"{root}/assets/hero.svg"


def test_validate_asset_name_rejects_paths() -> None:
    from fastapi import HTTPException

    assert _validate_asset_name("hero.svg") == "hero.svg"
    try:
        _validate_asset_name("../secret")
        raise AssertionError("expected 422")
    except HTTPException as exc:
        assert exc.status_code == 422
    try:
        _validate_asset_name(".gitkeep")
        raise AssertionError("expected 422")
    except HTTPException as exc:
        assert exc.status_code == 422


def test_project_tree_and_asset_roundtrip(monkeypatch) -> None:
    sc = SourceControlService(InMemoryAdapter())
    client = _slides_client(monkeypatch, sc)
    created = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "Untitled presentation",
            "slug": "untitled-local",
            "template_id": "minimal-light-v1",
        },
    )
    assert created.status_code == 200, created.text
    repo_id = _repo_id()
    sc.upsert_file(
        repo_id=repo_id,
        path="slides/ws-other/other-deck/deck.html",
        content="<html></html>",
        message="junk other project",
        branch="main",
    )
    tree = client.get(
        "/slides/projects/untitled-local/tree",
        params={"workspace_id": "ws-test"},
    )
    assert tree.status_code == 200, tree.text
    body = tree.json()
    assert [e["name"] for e in body["entries"]] == ["assets", "deck.html", "project.json"]
    assert body["assets"] == []
    saved = client.put(
        "/slides/projects/untitled-local/assets/hero.svg",
        json={
            "workspace_id": "ws-test",
            "content": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["path"] == "slides/ws-test/untitled-local/assets/hero.svg"
    tree2 = client.get(
        "/slides/projects/untitled-local/tree",
        params={"workspace_id": "ws-test"},
    )
    assert tree2.status_code == 200, tree2.text
    assert [a["name"] for a in tree2.json()["assets"]] == ["hero.svg"]
    got = client.get(
        "/slides/projects/untitled-local/assets/hero.svg",
        params={"workspace_id": "ws-test"},
    )
    assert got.status_code == 200, got.text
    assert "<svg" in got.json()["content"]
    templates = client.get("/slides/templates", params={"workspace_id": "ws-test"})
    light = next(t for t in templates.json() if t["id"] == "minimal-light-v1")
    assert any(f["name"] == "deck.html" for f in light["files"])
    renamed = client.patch(
        "/slides/projects/untitled-local",
        json={"workspace_id": "ws-test", "title": "Hormuz brief"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Hormuz brief"
    assert renamed.json()["slug"] == "untitled-local"
    assert renamed.json()["deck_path"] == "slides/ws-test/untitled-local/deck.html"
    listed = client.get("/slides/projects", params={"workspace_id": "ws-test"})
    assert any(p["title"] == "Hormuz brief" for p in listed.json())
