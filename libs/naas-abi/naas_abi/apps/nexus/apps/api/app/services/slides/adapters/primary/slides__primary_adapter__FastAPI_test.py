"""Unit tests for Slides helpers (no live Forgejo)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import SlidesTemplateSourceConfig
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary import (
    slides__primary_adapter__FastAPI as slides_api,
)
from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary.slides__primary_adapter__FastAPI import (
    _assets_dir,
    _assets_gitkeep_path,
    _branch_for,
    _coder_workspace_name,
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
    _wait_for_sidecar,
    _write_deck_via_sidecar,
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
from pydantic import ValidationError


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
    assert "abi/pitch-dark-v1" in ids
    assert "abi/minimal-light-v1" in ids
    assert "abi/executive-v1" in ids
    assert len(ids) == 3
    assert ids[0] == "abi/minimal-light-v1"
    records = _list_seed_template_records()
    by_id = {r["id"]: r for r in records}
    assert by_id["abi/minimal-light-v1"]["name"] == "Minimal Light"
    assert by_id["abi/pitch-dark-v1"]["preview_bg"].startswith("#")
    light_slides = by_id["abi/minimal-light-v1"]["slides"]
    titles = [s["title"] for s in light_slides]
    assert "Presentation Title" in titles
    assert "What we will cover" in titles
    assert any(s.get("eyebrow") == "Agenda" for s in light_slides)
    assert by_id["abi/minimal-light-v1"]["assets"]
    for tid in ("pitch-dark-v1", "minimal-light-v1", "executive-v1"):
        # Bare, as a project.json written before namespaces would have it.
        html = _load_seed_html(tid)
        assert "function buildPptx" in html
        assert "NEXUS_SLIDES_PPTX_FROM_DOM_V1" in html
        assert 'class="deck"' in html
        assert 'class="slide' in html
        assert "deck-menubar" in html
        assert _load_seed_html(f"abi/{tid}") == html


def _write_template_dir(directory: Path, stem: str, name: str) -> Path:
    """One seed deck plus its catalog row, the shape a source must satisfy."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "catalog.json").write_text(
        json.dumps({"templates": [{"id": stem, "name": name}]}),
        encoding="utf-8",
    )
    (directory / f"{stem}.html").write_text(
        f'<main class="deck"><section class="slide"><h1>{name}</h1></section></main>',
        encoding="utf-8",
    )
    return directory


def _configure_sources(monkeypatch, *sources: tuple[str, Path]) -> None:
    monkeypatch.setattr(
        slides_api.settings,
        "slides_template_sources",
        [
            SlidesTemplateSourceConfig(namespace=namespace, path=str(path))
            for namespace, path in sources
        ],
        raising=False,
    )


def test_templates_need_no_configured_source(monkeypatch) -> None:
    """The zero-config install is the one that must not break.

    ABI ships its own seeds. An install that configures nothing still has to
    serve a full picker, or New Presentation opens onto an empty menu.
    """
    _configure_sources(monkeypatch)

    ids = _discover_seed_ids()

    assert ids == ["abi/minimal-light-v1", "abi/pitch-dark-v1", "abi/executive-v1"]
    assert {row["source"] for row in _list_seed_template_records()} == {"abi"}
    assert "function buildPptx" in _load_seed_html("abi/minimal-light-v1")


def test_a_configured_source_adds_its_own_namespace(tmp_path, monkeypatch) -> None:
    """A source names itself, so ABI never spells a consumer's name."""
    directory = _write_template_dir(tmp_path / "acme", "tenant-only-v1", "Tenant Only")
    _configure_sources(monkeypatch, ("acme", directory))

    ids = _discover_seed_ids()

    assert "abi/minimal-light-v1" in ids
    assert "acme/tenant-only-v1" in ids
    assert "acme/minimal-light-v1" not in ids
    assert "Tenant Only" in _load_seed_html("acme/tenant-only-v1")
    row = next(r for r in _list_seed_template_records() if r["source"] == "acme")
    assert row["id"] == "acme/tenant-only-v1"
    assert row["name"] == "Tenant Only"
    assert row["origin"] == str(directory)


def test_configured_sources_do_not_leak_into_each_other(tmp_path, monkeypatch) -> None:
    """Two sources may ship the same stem. The namespace is what separates them."""
    _configure_sources(
        monkeypatch,
        ("acme", _write_template_dir(tmp_path / "a", "house-style-v1", "Acme House")),
        ("globex", _write_template_dir(tmp_path / "g", "house-style-v1", "Globex House")),
    )

    ids = _discover_seed_ids()

    assert "acme/house-style-v1" in ids
    assert "globex/house-style-v1" in ids
    assert "Acme House" in _load_seed_html("acme/house-style-v1")
    assert "Globex House" in _load_seed_html("globex/house-style-v1")
    with pytest.raises(HTTPException) as caught:
        _load_seed_html("abi/house-style-v1")
    assert caught.value.status_code == 404


def test_an_unknown_namespace_is_a_miss_not_a_syntax_error(monkeypatch) -> None:
    """Which namespaces exist is configuration, so the grammar cannot judge it."""
    _configure_sources(monkeypatch)

    with pytest.raises(HTTPException) as caught:
        _load_seed_html("nobody/minimal-light-v1")

    assert caught.value.status_code == 404


@pytest.mark.parametrize("namespace", ["abi", "ABI", "with space", "", "under_score"])
def test_a_source_namespace_is_refused_at_config_time(namespace: str) -> None:
    """Fail the boot, not the picker.

    ``abi`` is ABI's own namespace, and a source claiming it would shadow the
    seeds every install depends on. A namespace that is not a kebab slug cannot
    round-trip through a template id. Both are typos in config.yaml, so they
    belong to the boot, where the message names the field.
    """
    with pytest.raises(ValidationError):
        SlidesTemplateSourceConfig(namespace=namespace, path="seeds/templates")


def test_a_missing_source_directory_does_not_hide_the_abi_seeds(
    tmp_path, monkeypatch
) -> None:
    """A stale path in config.yaml must degrade to ABI's seeds, not to nothing."""
    _configure_sources(monkeypatch, ("acme", tmp_path / "does-not-exist"))

    ids = _discover_seed_ids()

    assert "abi/minimal-light-v1" in ids
    assert not [tid for tid in ids if tid.startswith("acme/")]


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
        id="user-1", email="admin@example.com", name="Test Admin"
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
    assert body["archived"] is False
    listed2 = client.get("/slides/projects", params={"workspace_id": "ws-test"})
    assert listed2.status_code == 200, listed2.text
    assert "untitled-local" in [p["slug"] for p in listed2.json()]
    templates = client.get("/slides/templates", params={"workspace_id": "ws-test"})
    assert templates.status_code == 200, templates.text
    catalog = templates.json()
    assert {t["id"] for t in catalog} >= {
        "abi/minimal-light-v1",
        "abi/pitch-dark-v1",
        "abi/executive-v1",
    }
    assert all(t["source"] == "abi" for t in catalog)
    light = next(t for t in catalog if t["id"] == "abi/minimal-light-v1")
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
    namespaced = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "Namespaced seed",
            "slug": "namespaced-seed",
            "template_id": "abi/executive-v1",
        },
    )
    assert namespaced.status_code == 200, namespaced.text
    assert namespaced.json()["template_id"] == "abi/executive-v1"


def test_patch_project_renames_and_archives_without_changing_slug(monkeypatch) -> None:
    sc = SourceControlService(InMemoryAdapter())
    client = _slides_client(monkeypatch, sc)
    created = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "Untitled presentation",
            "slug": "untitled-patch",
            "template_id": "minimal-light-v1",
        },
    )
    assert created.status_code == 200, created.text
    slug = created.json()["slug"]
    assert slug == "untitled-patch"

    empty = client.patch(
        f"/slides/projects/{slug}",
        json={"workspace_id": "ws-test"},
    )
    assert empty.status_code == 422

    renamed = client.patch(
        f"/slides/projects/{slug}",
        json={"workspace_id": "ws-test", "title": "Board update"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["slug"] == slug
    assert renamed.json()["title"] == "Board update"
    assert renamed.json()["archived"] is False
    assert renamed.json()["deck_path"] == "slides/ws-test/untitled-patch/deck.html"

    archived = client.patch(
        f"/slides/projects/{slug}",
        json={"workspace_id": "ws-test", "archived": True},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True
    assert archived.json()["slug"] == slug
    assert archived.json()["title"] == "Board update"

    listed = client.get("/slides/projects", params={"workspace_id": "ws-test"})
    assert listed.status_code == 200, listed.text
    row = next(p for p in listed.json() if p["slug"] == slug)
    assert row["archived"] is True
    assert row["title"] == "Board update"

    restored = client.patch(
        f"/slides/projects/{slug}",
        json={"workspace_id": "ws-test", "archived": False},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["archived"] is False
    assert restored.json()["slug"] == slug

    missing = client.patch(
        "/slides/projects/no-such-deck",
        json={"workspace_id": "ws-test", "title": "Nope"},
    )
    assert missing.status_code == 404


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

    def fake_probe(base, secret, *, timeout_s=2.0):
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


def test_slides_template_names_match_local_directory_adapter(tmp_path) -> None:
    """The no-Docker adapter advertises one template; slides must accept it.

    Without this the runtime probe never picks a template and the deck view
    shows a permanent "Coder runtime unavailable" banner.
    """
    from naas_abi_core.services.coding_environment.adapters.secondary.LocalDirectoryAdapter import (
        LocalDirectoryAdapter,
    )

    adapter = LocalDirectoryAdapter(workspaces_root=str(tmp_path / "ws"))
    advertised = {t.name for t in adapter.list_templates()}
    assert advertised & set(slides_api._SLIDES_TEMPLATE_NAMES), (
        f"none of {slides_api._SLIDES_TEMPLATE_NAMES} match {advertised}"
    )


class _FakeRepoSC:
    def __init__(self, clone_url: str) -> None:
        self._clone_url = clone_url

    def ensure_repo(self, *, owner: str, name: str, **_kwargs):
        from naas_abi_core.services.source_control.SourceControlPorts import Repo

        return Repo(
            id=f"{owner}/{name}",
            name=name,
            owner=owner,
            default_branch="main",
            clone_url=self._clone_url,
            html_url=self._clone_url,
            private=True,
            empty=False,
        )


def test_clone_url_uses_the_local_checkout_when_git_is_on_disk() -> None:
    """local_git has no Forgejo server, so provisioning must clone file://.

    Otherwise the sidecar clone targets the Docker host forgejo:3000, fails,
    and the deck view shows "Coder runtime unavailable".
    """
    sc = _FakeRepoSC("file:///tmp/git/abi/monorepo")
    url = slides_api._git_clone_url(
        sc, "abi/monorepo", username="git", token="local"
    )
    assert url == "file:///tmp/git/abi/monorepo"
    assert "forgejo" not in url
    # Three slashes and no fourth component: the username and token must not be
    # spliced into the authority, which for a file:// URL has no server to
    # authenticate against and makes git reject the clone.
    assert url.startswith("file:///")


def test_clone_url_keeps_authenticated_http_for_a_real_forge() -> None:
    sc = _FakeRepoSC("http://forgejo:3000/abi/monorepo.git")
    url = slides_api._git_clone_url(
        sc, "abi/monorepo", username="git", token="tok en"
    )
    assert url.startswith("http://git:tok%20en@")
    assert url.endswith("/abi/monorepo.git")


def test_clone_url_falls_back_when_the_adapter_cannot_describe_the_repo() -> None:
    class _Broken:
        def ensure_repo(self, **_kwargs):
            raise RuntimeError("nope")

    url = slides_api._git_clone_url(
        _Broken(), "abi/monorepo", username="git", token="t"
    )
    assert url.startswith("http://git:t@")


_LOCAL_SIDECAR_BASE = "http://127.0.0.1:18999"
_LOCAL_SIDECAR_SECRET = "secret-baked-by-the-adapter"


class _FakeLocalCoding:
    """Stands in for CodingEnvironmentService over LocalDirectoryAdapter.

    The local adapter picks its own loopback port and secret at provision
    time, then reports them through ``get_runtime_binding``. The Coder naming
    convention (``coder-<user>-<name>:8378``) does not exist here.
    """

    def __init__(self) -> None:
        self.provisioned: list[dict] = []
        self._adapter = object()

    def list_templates(self):
        from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
            WorkspaceTemplate,
        )

        return [
            WorkspaceTemplate(
                id="local-directory",
                name="local-directory",
                active_version_id="local",
            )
        ]

    def ensure_user(self, *, external_id: str, email: str, username) -> str:
        del email, username
        return external_id

    def list_environments(self, *, user_id: str):
        del user_id
        return []

    def provision(self, *, user_id: str, template_id: str, name: str, params=None):
        from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
            WorkspaceStatus,
        )

        del user_id, template_id
        self.provisioned.append(dict(params or {}))
        return WorkspaceStatus(
            id="env-local-1", name=name, phase="running", agent_ready=True
        )

    def get_runtime_binding(self, *, workspace_id: str):
        del workspace_id
        return _LOCAL_SIDECAR_BASE, _LOCAL_SIDECAR_SECRET

    def get_harness_binding(self, *, workspace_id: str):
        del workspace_id
        return "http://127.0.0.1:18202"

    def get_workspace_ui_url(self, *, workspace_id: str):
        del workspace_id
        return None


def _only_the_local_sidecar_answers(base, secret, *, timeout_s=2.0):
    del timeout_s
    return (base, secret) in {
        (_LOCAL_SIDECAR_BASE, _LOCAL_SIDECAR_SECRET),
        (_REBOUND_SIDECAR_BASE, _REBOUND_SIDECAR_SECRET),
    }


def test_runtime_binds_the_sidecar_the_adapter_actually_started(monkeypatch) -> None:
    """Slides must ask the adapter where the sidecar is, like the Code path.

    ``/coding-environments/sandbox/runtime`` reads ``get_runtime_binding`` and
    gets ``http://127.0.0.1:<port>``. Slides instead derived a Coder DNS name
    (``coder-<user>-<workspace>:8378``) that never resolves without Docker, so
    every probe failed and the deck showed "Coder sidecar not reachable".
    """
    sc = SourceControlService(InMemoryAdapter())
    coding = _FakeLocalCoding()
    client = _slides_client(monkeypatch, sc)
    monkeypatch.setattr(slides_api, "_get_coding_environment", lambda _r: coding)
    monkeypatch.setattr(slides_api, "_probe_sidecar", _only_the_local_sidecar_answers)
    monkeypatch.setattr(slides_api.time, "sleep", lambda *_: None)

    created = client.post(
        "/slides/projects",
        json={"workspace_id": "ws-test", "title": "Runtime deck", "slug": "runtime-deck"},
    )
    assert created.status_code == 200, created.text

    runtime = client.post(
        "/slides/projects/runtime-deck/runtime",
        params={"workspace_id": "ws-test"},
    )
    assert runtime.status_code == 200, runtime.text
    body = runtime.json()
    assert body["ensured"] is True
    assert body["sidecar_ready"] is True, body
    assert body["detail"] is None, body


def test_runtime_reports_the_adapter_binding_for_lookup(monkeypatch) -> None:
    """The binding Slides persists must be the one Abi can call back on."""
    sc = SourceControlService(InMemoryAdapter())
    coding = _FakeLocalCoding()
    client = _slides_client(monkeypatch, sc)
    monkeypatch.setattr(slides_api, "_get_coding_environment", lambda _r: coding)
    monkeypatch.setattr(slides_api, "_probe_sidecar", _only_the_local_sidecar_answers)
    monkeypatch.setattr(slides_api.time, "sleep", lambda *_: None)

    captured: dict[str, str] = {}
    real_wait = slides_api._wait_for_sidecar

    def _record(base, secret, **kwargs):
        captured["base"] = str(base)
        captured["secret"] = str(secret)
        return real_wait(base, secret, **kwargs)

    monkeypatch.setattr(slides_api, "_wait_for_sidecar", _record)

    client.post(
        "/slides/projects",
        json={"workspace_id": "ws-test", "title": "Bound deck", "slug": "bound-deck"},
    )
    client.post(
        "/slides/projects/bound-deck/runtime", params={"workspace_id": "ws-test"}
    )
    assert captured.get("base") == _LOCAL_SIDECAR_BASE, captured
    assert captured.get("secret") == _LOCAL_SIDECAR_SECRET, captured


_REBOUND_SIDECAR_BASE = "http://127.0.0.1:19001"
_REBOUND_SIDECAR_SECRET = "secret-after-the-restart"


class _StaleThenAdoptCoding(_FakeLocalCoding):
    """Adapter that lost its in-memory record but still owns the workspace.

    This is what an API restart looks like: the Nexus row still points at
    environment ``env-local-1``, ``get_status`` no longer knows it, and the
    re-provision path re-adopts the very same id by name. The restarted
    sidecar lands on a different loopback port with a different secret, so
    the stored binding has to be replaced, not kept.
    """

    def __init__(self, environment_id: str = "env-local-1") -> None:
        super().__init__()
        self._environment_id = environment_id
        self._name = ""
        self.restarted = False

    def _status(self):
        from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
            WorkspaceStatus,
        )

        return WorkspaceStatus(
            id=self._environment_id,
            name=self._name,
            phase="running",
            agent_ready=True,
        )

    def get_runtime_binding(self, *, workspace_id: str):
        del workspace_id
        if self.restarted:
            return _REBOUND_SIDECAR_BASE, _REBOUND_SIDECAR_SECRET
        return _LOCAL_SIDECAR_BASE, _LOCAL_SIDECAR_SECRET

    def get_status(self, *, workspace_id: str):
        from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
            WorkspaceNotFoundError,
        )

        if not self._name:
            raise WorkspaceNotFoundError(workspace_id)
        return self._status()

    def provision(self, *, user_id: str, template_id: str, name: str, params=None):
        del user_id, template_id
        self.provisioned.append(dict(params or {}))
        self._name = name
        return self._status()

    def list_environments(self, *, user_id: str):
        del user_id
        return [self._status()] if self._name else []

    def forget(self) -> None:
        """Drop the in-memory record the way an API restart would."""
        self._name = ""
        self.restarted = True


def _sqlite_slides_client(monkeypatch, source_control, session):
    app = FastAPI()
    app.state.source_control = source_control
    app.include_router(slides_api.router, prefix="/slides")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="admin@example.com", name="Test Admin"
    )

    async def _session():
        yield session

    app.dependency_overrides[get_db] = _session

    async def _allow(user_id: str, workspace_id: str) -> str:
        return "owner"

    monkeypatch.setattr(slides_api, "require_workspace_access", _allow)
    monkeypatch.setattr(slides_api, "_probe_sidecar", _only_the_local_sidecar_answers)
    monkeypatch.setattr(slides_api.time, "sleep", lambda *_: None)
    return TestClient(app)


def test_runtime_rebinds_when_the_same_environment_is_adopted_twice(
    monkeypatch, tmp_path
) -> None:
    """Re-provisioning the same environment id must update, not collide.

    The persist step only deleted the prior row ``if old.id != status.id``,
    so the one case it had to handle -- adopting the same environment -- hit
    ``UNIQUE constraint failed: coding_environments.id``, rolled back, and
    left Slides with no runtime binding at all.
    """
    import anyio
    from naas_abi.apps.nexus.apps.api.app.models import CodingEnvironmentModel
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}"

    async def _scenario():
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(CodingEnvironmentModel.__table__.create)
        session = async_sessionmaker(engine, expire_on_commit=False)()

        sc = SourceControlService(InMemoryAdapter())
        coding = _StaleThenAdoptCoding()
        client = _sqlite_slides_client(monkeypatch, sc, session)
        monkeypatch.setattr(slides_api, "_get_coding_environment", lambda _r: coding)

        def _call() -> None:
            client.post(
                "/slides/projects",
                json={
                    "workspace_id": "ws-test",
                    "title": "Adopted deck",
                    "slug": "adopted-deck",
                },
            )
            for _ in range(2):
                res = client.post(
                    "/slides/projects/adopted-deck/runtime",
                    params={"workspace_id": "ws-test"},
                )
                assert res.status_code == 200, res.text
                # Between calls the adapter forgets the workspace, so the next
                # ensure re-adopts the same environment id on a new port.
                coding.forget()

        await anyio.to_thread.run_sync(_call)

        rows = (
            (await session.execute(select(CodingEnvironmentModel)))
            .scalars()
            .all()
        )
        count = len(rows)
        base = rows[0].sidecar_base if rows else None
        secret = rows[0].sidecar_secret if rows else None
        created = rows[0].created_at if rows else None
        await session.close()
        await engine.dispose()
        return count, base, secret, created

    count, base, secret, created = anyio.run(_scenario)
    assert count == 1, f"expected one runtime row, found {count}"
    assert base == _REBOUND_SIDECAR_BASE, base
    assert secret == _REBOUND_SIDECAR_SECRET, secret
    # merge() must not blank the insert-only column it was never given.
    assert created is not None


_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _write_folder_template(directory: Path, stem: str, name: str) -> Path:
    """Catalog folder: ``{stem}/{stem}.html`` plus ``{stem}/assets/hero.png``."""
    folder = directory / stem
    assets = folder / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (directory / "catalog.json").write_text(
        json.dumps({"templates": [{"id": stem, "name": name}]}),
        encoding="utf-8",
    )
    (folder / f"{stem}.html").write_text(
        f'<!doctype html><html><body><img src="assets/hero.png" alt="{name}"></body></html>',
        encoding="utf-8",
    )
    (assets / "hero.png").write_bytes(_TINY_PNG)
    return directory


def test_create_and_apply_template_copies_catalog_assets(
    tmp_path, monkeypatch
) -> None:
    source_dir = _write_folder_template(tmp_path / "office", "pixel-v1", "Pixel")
    _configure_sources(monkeypatch, ("office", source_dir))

    sc = SourceControlService(InMemoryAdapter())
    client = _slides_client(monkeypatch, sc)
    created = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "Pixel deck",
            "slug": "pixel-deck",
            "template_id": "office/pixel-v1",
        },
    )
    assert created.status_code == 200, created.text
    deck = client.get(
        "/slides/projects/pixel-deck/deck",
        params={"workspace_id": "ws-test"},
    )
    assert deck.status_code == 200, deck.text
    html = deck.json()["html"]
    assert "data:image/" not in html
    assert 'src="assets/hero.png"' in html

    commits = sc.list_commits(
        repo_id=slides_api._repo_id(), ref="slides/ws-test/pixel-deck", limit=20
    )
    seed_commits = [c for c in commits if "Create slides project" in c.message]
    assert len(seed_commits) == 1

    asset = client.get(
        "/slides/projects/pixel-deck/assets/hero.png",
        params={"workspace_id": "ws-test"},
    )
    assert asset.status_code == 200, asset.text
    assert asset.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert "image/png" in (asset.headers.get("content-type") or "")

    traversal = client.get(
        "/slides/projects/pixel-deck/assets/..png",
        params={"workspace_id": "ws-test"},
    )
    assert traversal.status_code == 422

    tree = client.get(
        "/slides/projects/pixel-deck/tree",
        params={"workspace_id": "ws-test"},
    )
    assert tree.status_code == 200, tree.text
    body = tree.json()
    assert body["embedded_images"] == 0
    assert "copied from the catalog" in (body.get("assets_note") or "")

    applied = client.post(
        "/slides/projects/pixel-deck/apply-template",
        json={"workspace_id": "ws-test", "template_id": "office/pixel-v1"},
    )
    assert applied.status_code == 200, applied.text
    assert "data:image/" not in applied.json()["html"]
    again = client.get(
        "/slides/projects/pixel-deck/assets/hero.png",
        params={"workspace_id": "ws-test"},
    )
    assert again.status_code == 200
    assert again.content[:8] == b"\x89PNG\r\n\x1a\n"
    apply_commits = [
        c
        for c in sc.list_commits(
            repo_id=slides_api._repo_id(), ref="slides/ws-test/pixel-deck", limit=20
        )
        if c.message.startswith("Apply template")
    ]
    assert len(apply_commits) == 1


def test_load_seed_html_reads_folder_template(tmp_path, monkeypatch) -> None:
    source_dir = _write_folder_template(tmp_path / "acme", "folder-deck-v1", "Folder")
    _configure_sources(monkeypatch, ("acme", source_dir))
    html = _load_seed_html("acme/folder-deck-v1")
    assert 'src="assets/hero.png"' in html
    assert "acme/folder-deck-v1" in _discover_seed_ids()


def test_slide_mutations_insert_delete_duplicate_reorder(monkeypatch) -> None:
    sc = SourceControlService(InMemoryAdapter())
    client = _slides_client(monkeypatch, sc)
    created = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "Mutation deck",
            "slug": "mutation-deck",
            "template_id": "minimal-light-v1",
        },
    )
    assert created.status_code == 200, created.text
    listed = client.get(
        "/slides/projects/mutation-deck/slides",
        params={"workspace_id": "ws-test"},
    )
    assert listed.status_code == 200, listed.text
    start = listed.json()
    assert start["ok"] is True
    assert start["section_count"] >= 2
    n = start["section_count"]

    inserted = client.post(
        "/slides/projects/mutation-deck/slides/insert",
        json={
            "workspace_id": "ws-test",
            "after_index": 0,
            "layout": "content",
            "title": "Risks",
        },
    )
    assert inserted.status_code == 200, inserted.text
    body = inserted.json()
    assert body["ok"] is True
    assert body["section_index"] == 1
    assert body["section_count"] == n + 1
    assert "Risks" in (body.get("html") or "")
    assert any(s.get("title") == "Risks" for s in body["slides"])

    duplicated = client.post(
        "/slides/projects/mutation-deck/slides/duplicate",
        json={"workspace_id": "ws-test", "index": 1},
    )
    assert duplicated.status_code == 200, duplicated.text
    assert duplicated.json()["section_count"] == n + 2
    assert duplicated.json()["section_index"] == 2

    reordered = client.post(
        "/slides/projects/mutation-deck/slides/reorder",
        json={"workspace_id": "ws-test", "from_index": 1, "to_index": 2},
    )
    assert reordered.status_code == 200, reordered.text
    assert reordered.json()["section_index"] == 2

    deleted = client.post(
        "/slides/projects/mutation-deck/slides/delete",
        json={"workspace_id": "ws-test", "index": 2},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["section_count"] == n + 1

    deck = client.get(
        "/slides/projects/mutation-deck/deck",
        params={"workspace_id": "ws-test"},
    )
    assert deck.status_code == 200
    assert "Risks" in deck.json()["html"]


def test_delete_last_slide_is_refused(monkeypatch) -> None:
    sc = SourceControlService(InMemoryAdapter())
    client = _slides_client(monkeypatch, sc)
    created = client.post(
        "/slides/projects",
        json={
            "workspace_id": "ws-test",
            "title": "One slide",
            "slug": "one-slide-deck",
            "template_id": "minimal-light-v1",
        },
    )
    assert created.status_code == 200, created.text
    listed = client.get(
        "/slides/projects/one-slide-deck/slides",
        params={"workspace_id": "ws-test"},
    )
    count = listed.json()["section_count"]
    for index in range(count - 1, 0, -1):
        gone = client.post(
            "/slides/projects/one-slide-deck/slides/delete",
            json={"workspace_id": "ws-test", "index": index},
        )
        assert gone.status_code == 200, gone.text
    last = client.post(
        "/slides/projects/one-slide-deck/slides/delete",
        json={"workspace_id": "ws-test", "index": 0},
    )
    assert last.status_code == 409
    assert "last slide" in last.json()["detail"].lower()
