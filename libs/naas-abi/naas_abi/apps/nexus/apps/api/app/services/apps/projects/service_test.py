from __future__ import annotations

import json
from typing import Any

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppAuthor,
    AppCommit,
    AppDraftStorePort,
    AppFile,
    AppFileError,
    AppFileNotFoundError,
    AppOrigin,
    AppProjectError,
    AppProjectExistsError,
    AppProjectKey,
    AppProjectNotFoundError,
    AppProjectRepositoryPort,
    AppRepoPublisherPort,
    AppSubmission,
    AppSubmitUnavailableError,
    ModuleAppSource,
    ModuleAppSourcePort,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
    normalize_app_path,
    skipped_on_import,
)

ALICE = AppAuthor(user_id="u-1", name="Alice", email="alice@example.com")
WS = "ws-1"


class FakeRepository(AppProjectRepositoryPort):
    def __init__(self) -> None:
        self.branches: dict[str, dict[str, bytes]] = {}
        self.metas: dict[str, dict[str, Any]] = {}
        self.commits: dict[str, list[AppCommit]] = {}

    def list_projects(self, workspace_id: str) -> list[tuple[str, str]]:
        prefix = AppProjectKey(workspace_id, "x").branch.rsplit("/", 1)[0] + "/"
        return [
            (name[len(prefix) :], self.commits[name][0].sha)
            for name in self.branches
            if name.startswith(prefix)
        ]

    def create(self, key: AppProjectKey) -> None:
        if key.branch in self.branches:
            raise AppProjectExistsError(key.slug)
        self.branches[key.branch] = {}
        self.commits[key.branch] = [AppCommit("sha-0", "branch", "nexus")]

    def read_meta(self, key: AppProjectKey) -> dict[str, Any] | None:
        return self.metas.get(key.branch)

    def head(self, key: AppProjectKey) -> str | None:
        commits = self.commits.get(key.branch)
        return commits[0].sha if commits else None

    def read_files(self, key: AppProjectKey) -> dict[str, bytes]:
        return dict(self.branches[key.branch])

    def commit(self, key, *, writes, deletes, meta, message, author) -> str:
        files = self.branches[key.branch]
        files.update(writes)
        for path in deletes:
            files.pop(path, None)
        if meta is not None:
            self.metas[key.branch] = json.loads(json.dumps(meta))
        sha = f"sha-{len(self.commits[key.branch])}"
        self.commits[key.branch].insert(0, AppCommit(sha, message, author.name))
        return sha

    def history(self, key: AppProjectKey, limit: int = 20) -> list[AppCommit]:
        return self.commits[key.branch][:limit]


class FakeDrafts(AppDraftStorePort):
    def __init__(self) -> None:
        self.files: dict[str, dict[str, bytes]] = {}
        self.states: dict[str, dict[str, Any]] = {}

    def read_state(self, key):
        return self.states.get(key.branch)

    def write_state(self, key, state):
        self.states[key.branch] = json.loads(json.dumps(state))

    def list_files(self, key):
        return [AppFile(p, len(d)) for p, d in sorted(self.files.get(key.branch, {}).items())]

    def read_file(self, key, path):
        return self.files.get(key.branch, {}).get(path)

    def write_file(self, key, path, data):
        self.files.setdefault(key.branch, {})[path] = data

    def delete_file(self, key, path):
        self.files.get(key.branch, {}).pop(path, None)

    def clear(self, key):
        self.files.pop(key.branch, None)
        self.states.pop(key.branch, None)

    def replace_all(self, key, files):
        self.clear(key)
        self.files[key.branch] = dict(files)


BUDGET_ORIGIN = AppOrigin(
    app_id="bob:budget",
    module_path="bob",
    app_name="budget",
    repo_path="src/bob/apps/sheets/budget",
    source_commit="abc123",
    kind="bundled",
    url="html:index.html",
)


class FakeModules(ModuleAppSourcePort):
    def get(self, app_id: str) -> ModuleAppSource | None:
        if app_id != "bob:budget":
            return None
        files = {
            "manifest.json": json.dumps({"name": "Budget", "url": "html:index.html"}).encode(),
            "index.html": b'<link href="budget.css"><script src="sheet.js"></script>',
            "budget.css": b"body{}",
            "sheet.js": b"1",
            "assets/logo.svg": b"<svg/>",
        }
        return ModuleAppSource(
            origin=BUDGET_ORIGIN,
            manifest=json.loads(files["manifest.json"]),
            files=files,
            skipped=(".gitignore",),
        )

    def module_targets(self) -> dict[str, str]:
        return {"bob": "src/bob/apps", "plans": "src/plans/apps"}


class FakePublisher(AppRepoPublisherPort):
    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.calls: list[dict[str, Any]] = []

    def describe(self) -> dict[str, Any]:
        return {"configured": self.configured, "repo": "org/bob", "base_branch": "dev"}

    def publish(self, **kwargs: Any) -> AppSubmission:
        self.calls.append(kwargs)
        return AppSubmission(
            branch=kwargs["branch"],
            url=f"https://github.com/org/bob/tree/{kwargs['branch']}",
            commit_sha="gh-1",
            target_path=kwargs["target_path"],
        )


def _service(**kwargs: Any) -> tuple[AppProjectsService, FakeRepository, FakeDrafts]:
    repo, drafts = FakeRepository(), FakeDrafts()
    service = AppProjectsService(
        repository=repo,
        drafts=drafts,
        module_source=kwargs.get("modules", FakeModules()),
        publisher=kwargs.get("publisher"),
        now=lambda: "2026-09-11T00:00:00+00:00",
    )
    return service, repo, drafts


# -- path rules ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("index.html", "index.html"),
        ("./css/app.css", "css/app.css"),
        ("/js/app.js", "js/app.js"),
        ("assets\\logo.png", "assets/logo.png"),
        ("functions/api/[id].js", "functions/api/[id].js"),
        ("_headers", "_headers"),
    ],
)
def test_paths_are_normalized(raw: str, clean: str) -> None:
    assert normalize_app_path(raw) == clean


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "../x.js",
        "a/../../b.js",
        ".env",
        "config/.dev.vars",
        ".git/config",
        "node_modules/x/index.js",
        "certs/server.pem",
        "id_rsa",
        "a\x00b.js",
        "a/" * 20 + "x.js",
        "x" * 300,
    ],
)
def test_paths_the_rules_refuse(raw: str) -> None:
    with pytest.raises(AppFileError):
        normalize_app_path(raw)


def test_import_skips_secrets_and_tooling() -> None:
    assert skipped_on_import(".dev.vars")
    assert skipped_on_import(".wrangler/state/v3/kv.sqlite")
    assert skipped_on_import("node_modules/wrangler/package.json")
    assert skipped_on_import("keys/service.key")
    assert not skipped_on_import("functions/api/otp.js")
    assert not skipped_on_import("wrangler.toml")


# -- create, edit, save -------------------------------------------------------


def test_create_seeds_a_static_starter_in_one_commit() -> None:
    service, repo, _ = _service()

    info = service.create_project(WS, title="Budget Tracker", author=ALICE)

    assert info.meta.slug == "budget-tracker"
    assert info.branch == "apps/ws-1/budget-tracker"
    assert info.entry == "index.html"
    assert not info.dirty
    names = {f.path for f in info.files}
    assert {"manifest.json", "index.html", "styles.css", "app.js"} <= names
    manifest = json.loads(service.read_file(info_key(info), "manifest.json"))
    assert manifest["name"] == "Budget Tracker"
    assert manifest["url"] == "html:index.html"
    assert len(repo.history(info_key(info))) == 2  # branch + seed
    assert repo.metas[info.branch]["workspace_id"] == WS


def test_create_picks_a_free_slug() -> None:
    service, _, _ = _service()
    service.create_project(WS, title="Demo", author=ALICE)
    assert service.create_project(WS, title="Demo", author=ALICE).meta.slug == "demo-2"
    # Route names next to /{slug} are never project slugs.
    assert (
        service.create_project(WS, title="Submit Config", author=ALICE).meta.slug
        == "submit-config-2"
    )


def info_key(info: Any) -> AppProjectKey:
    return AppProjectKey(info.meta.workspace_id, info.meta.slug)


def test_edits_land_in_the_draft_until_save() -> None:
    service, repo, _ = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))

    service.write_file(key, "styles.css", "h1{color:red}")
    service.write_file(key, "js/chart.js", b"export {}")
    service.delete_file(key, "app.js")

    assert service.get_project(key).dirty
    assert repo.branches[key.branch]["styles.css"] != b"h1{color:red}"

    commit = service.save(key, author=ALICE, message="style: red title")

    assert commit is not None and commit.message == "style: red title"
    saved = repo.branches[key.branch]
    assert saved["styles.css"] == b"h1{color:red}"
    assert saved["js/chart.js"] == b"export {}"
    assert "app.js" not in saved
    assert not service.get_project(key).dirty
    assert service.save(key, author=ALICE) is None  # nothing changed


def test_discard_restores_the_saved_copy() -> None:
    service, _, _ = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    before = service.read_file(key, "index.html")
    service.write_file(key, "index.html", "<p>scratch</p>")
    service.write_file(key, "extra.js", "1")

    service.discard(key)

    assert service.read_file(key, "index.html") == before
    with pytest.raises(AppFileNotFoundError):
        service.read_file(key, "extra.js")
    assert not service.get_project(key).dirty


def test_draft_hydrates_from_the_saved_branch() -> None:
    service, _, drafts = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    drafts.clear(key)  # e.g. a fresh object store

    assert service.read_file(key, "index.html").startswith(b"<!doctype html>")
    assert not service.get_project(key).dirty


def test_a_project_of_another_workspace_is_not_found() -> None:
    service, _, _ = _service()
    service.create_project(WS, title="Demo", author=ALICE)
    with pytest.raises(AppProjectNotFoundError):
        service.read_file(AppProjectKey("ws-2", "demo"), "index.html")


def test_oversize_files_are_refused() -> None:
    service, _, _ = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    with pytest.raises(AppFileError):
        service.write_file(key, "big.js", b"x" * (service.max_file_bytes + 1))


def test_list_projects_skips_archived_and_foreign_meta() -> None:
    service, repo, _ = _service()
    service.create_project(WS, title="One", author=ALICE)
    two = info_key(service.create_project(WS, title="Two", author=ALICE))
    service.update_project(two, author=ALICE, archived=True)

    assert [p.meta.slug for p in service.list_projects(WS)] == ["one"]
    assert {p.meta.slug for p in service.list_projects(WS, include_archived=True)} == {
        "one",
        "two",
    }


# -- duplicate a module app (edit works like create) -------------------------


def test_edit_duplicates_the_module_app_with_its_origin() -> None:
    service, repo, _ = _service()

    info = service.import_module_app(WS, app_id="bob:budget", author=ALICE)

    key = info_key(info)
    assert info.meta.slug == "budget"
    assert info.meta.title == "Budget"
    assert info.meta.origin is not None
    assert info.meta.origin.repo_path == "src/bob/apps/sheets/budget"
    assert set(info.meta.origin.imported_files) == {
        "manifest.json",
        "index.html",
        "budget.css",
        "sheet.js",
        "assets/logo.svg",
    }
    assert repo.branches[key.branch]["sheet.js"] == b"1"
    assert info.entry == "index.html"
    assert not info.dirty


def test_edit_of_an_unknown_app_is_not_found() -> None:
    service, _, _ = _service()
    with pytest.raises(AppProjectNotFoundError):
        service.import_module_app(WS, app_id="bob:nope", author=ALICE)


# -- preview + checks ---------------------------------------------------------


def test_preview_serves_the_entry_and_live_files() -> None:
    service, _, _ = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    service.write_file(key, "styles.css", "h1{color:red}")

    body, path = service.preview_file(key, "")
    assert path == "index.html" and b"styles.css" in body
    assert service.preview_file(key, "styles.css")[0] == b"h1{color:red}"
    with pytest.raises(AppFileNotFoundError):
        service.preview_file(key, "missing.js")


def test_check_flags_manifest_entry_and_links() -> None:
    service, _, _ = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    service.write_file(
        key,
        "index.html",
        '<link href="missing.css"><script src="/abs.js"></script>'
        '<a href="https://example.com">x</a><img src="data:image/png;base64,AA">',
    )
    service.write_file(key, "manifest.json", '{"url": "html:start.html"}')

    issues = [(i.level, i.path, i.message) for i in service.check(key)]
    messages = [m for _, _, m in issues]

    assert any(lvl == "error" and "name" in m for lvl, _, m in issues)
    assert any(lvl == "error" and "start.html" in m for lvl, _, m in issues)
    assert any("missing.css" in m for m in messages)
    assert any("/abs.js" in m for m in messages)
    assert not any("example.com" in m or "data:" in m for m in messages)


def test_check_is_clean_on_the_starter() -> None:
    service, _, _ = _service()
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    assert [i for i in service.check(key) if i.level != "info"] == []


# -- submit to the source repository ------------------------------------------


def test_submit_needs_a_configured_publisher() -> None:
    service, _, _ = _service(publisher=FakePublisher(configured=False))
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    with pytest.raises(AppSubmitUnavailableError):
        service.submit(key, author=ALICE)
    service_without, _, _ = _service()
    key = info_key(service_without.create_project(WS, title="Demo", author=ALICE))
    with pytest.raises(AppSubmitUnavailableError):
        service_without.submit(key, author=ALICE)


def test_submit_an_edited_module_app_to_its_origin_path() -> None:
    publisher = FakePublisher()
    service, repo, _ = _service(publisher=publisher)
    key = info_key(service.import_module_app(WS, app_id="bob:budget", author=ALICE))
    service.write_file(key, "budget.css", "body{color:red}")
    service.delete_file(key, "sheet.js")

    submission = service.submit(key, author=ALICE)

    call = publisher.calls[0]
    assert call["branch"] == "nexus-apps/ws-1/budget"
    assert call["target_path"] == "src/bob/apps/sheets/budget"
    assert call["deletes"] == ["sheet.js"]  # only what the user removed
    assert call["writes"]["budget.css"] == b"body{color:red}"
    assert "sheet.js" not in call["writes"]
    assert submission.url and submission.url.endswith("nexus-apps/ws-1/budget")
    # Saved first, and the submission is recorded on the project.
    assert repo.branches[key.branch]["budget.css"] == b"body{color:red}"
    assert repo.metas[key.branch]["submission"]["branch"] == "nexus-apps/ws-1/budget"
    assert service.get_project(key).meta.submission is not None


def test_submit_a_new_app_under_the_chosen_module() -> None:
    publisher = FakePublisher()
    service, _, _ = _service(publisher=publisher)
    key = info_key(service.create_project(WS, title="Team Map", author=ALICE))

    service.submit(key, author=ALICE, module="plans")

    call = publisher.calls[0]
    assert call["target_path"] == "src/plans/apps/team-map"
    assert call["deletes"] == []
    assert set(call["writes"]) >= {"manifest.json", "index.html"}


def test_submit_refuses_an_unknown_module() -> None:
    service, _, _ = _service(publisher=FakePublisher())
    key = info_key(service.create_project(WS, title="Demo", author=ALICE))
    with pytest.raises(AppProjectError, match="nope"):
        service.submit(key, author=ALICE, module="nope")
