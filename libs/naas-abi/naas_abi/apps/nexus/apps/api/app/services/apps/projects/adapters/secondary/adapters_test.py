from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.github import (
    GitHubAppRepoPublisher,
    git_blob_sha,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.module_apps import (
    ModuleAppSourceDisk,
    head_commit,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.object_storage import (
    AppDraftStoreObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.source_control import (
    AppProjectRepositoryGit,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppAuthor,
    AppProjectError,
    AppProjectExistsError,
    AppProjectKey,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

KEY = AppProjectKey("ws-1", "demo")
ALICE = AppAuthor("u-1", "Alice", "alice@example.com")


# -- object storage draft -----------------------------------------------------


def test_draft_store_round_trip(tmp_path: Path) -> None:
    store = AppDraftStoreObjectStorage(
        ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    )
    assert store.read_state(KEY) is None
    assert store.list_files(KEY) == []

    store.replace_all(KEY, {"index.html": b"<p>1</p>", "css/app.css": b"a{}"})
    store.write_file(KEY, "js/app.js", b"1")
    store.delete_file(KEY, "css/app.css")
    store.write_state(KEY, {"dirty": True})

    assert [(f.path, f.size) for f in store.list_files(KEY)] == [
        ("index.html", 8),
        ("js/app.js", 1),
    ]
    assert store.read_file(KEY, "js/app.js") == b"1"
    assert store.read_file(KEY, "css/app.css") is None
    assert store.read_state(KEY) == {"dirty": True}

    store.clear(KEY)
    assert store.list_files(KEY) == []
    assert store.read_state(KEY) is None


# -- git repository -----------------------------------------------------------


def _git_repo() -> AppProjectRepositoryGit:
    sc = SourceControlService(InMemoryAdapter())
    sc.ensure_repo(owner="abi", name="monorepo")
    return AppProjectRepositoryGit(sc, "abi/monorepo")


def test_git_repository_branch_per_project() -> None:
    repo = _git_repo()
    repo.create(KEY)
    with pytest.raises(AppProjectExistsError):
        repo.create(KEY)

    sha = repo.commit(
        KEY,
        writes={"index.html": b"<p>1</p>", "css/app.css": b"a{}"},
        deletes=[],
        meta={"slug": "demo", "workspace_id": "ws-1", "title": "Demo"},
        message="seed",
        author=ALICE,
    )

    assert repo.list_projects("ws-1") == [("demo", sha)]
    assert repo.list_projects("ws-2") == []
    assert repo.read_meta(KEY)["title"] == "Demo"
    assert repo.read_files(KEY) == {"index.html": b"<p>1</p>", "css/app.css": b"a{}"}
    assert repo.history(KEY)[0].message == "seed"


def test_service_end_to_end_on_real_adapters(tmp_path: Path) -> None:
    service = AppProjectsService(
        repository=_git_repo(),
        drafts=AppDraftStoreObjectStorage(
            ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        ),
    )
    key = AppProjectKey(
        "ws-1", service.create_project("ws-1", title="Demo", author=ALICE).meta.slug
    )
    service.write_file(key, "styles.css", "h1{color:red}")
    service.delete_file(key, "app.js")
    assert service.save(key, author=ALICE) is not None

    service.drafts.clear(key)  # hydrate back from git
    names = {f.path for f in service.list_files(key)}
    assert "app.js" not in names
    assert service.read_file(key, "styles.css") == b"h1{color:red}"


# -- module apps on disk ------------------------------------------------------


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


def test_module_app_source_reads_the_catalog_folder(tmp_path: Path) -> None:
    project = tmp_path / "bob"
    app_dir = project / "src/bob/apps/sheets/budget"
    _tree(
        app_dir,
        {
            "manifest.json": json.dumps({"name": "Budget", "url": "html:index.html"}),
            "index.html": "<p>b</p>",
            "assets/logo.svg": "<svg/>",
            ".dev.vars": "SECRET=1",
            "node_modules/x/index.js": "x",
        },
    )
    (project / ".git").mkdir()
    (project / ".git/HEAD").write_text("ref: refs/heads/dev\n")
    (project / ".git/refs/heads").mkdir(parents=True)
    (project / ".git/refs/heads/dev").write_text("abc123\n")

    source = ModuleAppSourceDisk(
        app_dir=lambda app_id: app_dir if app_id == "bob:budget" else None,
        modules=list,
        project_root=project,
    )

    got = source.get("bob:budget")

    assert got is not None
    assert set(got.files) == {"manifest.json", "index.html", "assets/logo.svg"}
    assert ".dev.vars" in got.skipped and "node_modules/" in got.skipped
    assert got.origin.repo_path == "src/bob/apps/sheets/budget"
    assert got.origin.source_commit == "abc123"
    assert got.origin.kind == "bundled"
    assert source.get("bob:missing") is None
    assert head_commit(project) == "abc123"


def test_module_targets_stay_in_the_host_repo(tmp_path: Path) -> None:
    project = tmp_path / "bob"
    (project / "src/bob").mkdir(parents=True)
    (project / ".git").mkdir()
    vendored = project / ".abi/libs/naas_abi"
    vendored.mkdir(parents=True)

    class Bob:
        module_root_path = str(project / "src/bob")

    class Vendored:
        module_root_path = str(vendored)

    Bob.__module__ = "bob"
    source = ModuleAppSourceDisk(
        app_dir=lambda _app_id: None,
        modules=lambda: [Bob(), Vendored()],
        project_root=project,
    )

    assert source.module_targets() == {"bob": "src/bob/apps"}


# -- GitHub publisher ---------------------------------------------------------


class FakeGitHub:
    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, Any]] = []

    def __call__(self, request: Any, timeout: int = 0) -> Any:
        method = request.get_method()
        path = request.full_url.split("/repos/org/bob", 1)[1]
        body = json.loads(request.data) if request.data else None
        self.calls.append((method, path, body))
        assert request.headers["Authorization"] == "Bearer t0k"
        for (m, prefix), payload in self.routes.items():
            if m == method and path.startswith(prefix):
                if payload == 404:
                    raise urllib.error.HTTPError(request.full_url, 404, "nf", {}, io.BytesIO(b"{}"))
                return _Response(payload)
        raise AssertionError(f"unrouted {method} {path}")


class _Response:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _publisher(routes: dict[tuple[str, str], Any]) -> tuple[GitHubAppRepoPublisher, FakeGitHub]:
    fake = FakeGitHub(routes)
    return (
        GitHubAppRepoPublisher(repo="org/bob", token="t0k", base_branch="dev", opener=fake),
        fake,
    )


def _routes(overrides: dict[tuple[str, str], Any] | None = None) -> dict[tuple[str, str], Any]:
    routes: dict[tuple[str, str], Any] = {
        ("GET", "/git/ref/heads/nexus-apps/"): 404,
        ("GET", "/git/ref/heads/dev"): {"object": {"sha": "base-1"}},
        ("GET", "/git/commits/"): {"tree": {"sha": "root-tree"}},
        ("GET", "/git/trees/root-tree"): {
            "tree": [{"path": "src", "type": "tree", "sha": "t-src"}]
        },
        ("GET", "/git/trees/t-src"): {"tree": [{"path": "app", "type": "tree", "sha": "t-app"}]},
        ("GET", "/git/trees/t-app"): {
            "tree": [
                {"path": "same.css", "type": "blob", "sha": git_blob_sha(b"same")},
                {"path": "old.js", "type": "blob", "sha": "blob-old"},
            ]
        },
        ("POST", "/git/blobs"): {"sha": "blob-new"},
        ("POST", "/git/trees"): {"sha": "tree-new"},
        ("POST", "/git/commits"): {"sha": "commit-new"},
        ("POST", "/git/refs"): {"ref": "x"},
        ("GET", "/pulls"): [],
        ("POST", "/pulls"): {"html_url": "https://github.com/org/bob/pull/7"},
    }
    routes.update(overrides or {})
    return routes


def test_publisher_is_off_without_a_token() -> None:
    publisher = GitHubAppRepoPublisher(repo="org/bob", token="", base_branch="dev")
    assert publisher.describe() == {"configured": False, "repo": "org/bob", "base_branch": "dev"}


def test_publish_creates_one_commit_with_only_real_changes() -> None:
    publisher, fake = _publisher(_routes())

    submission = publisher.publish(
        branch="nexus-apps/ws-1/app",
        target_path="src/app",
        writes={"same.css": b"same", "index.html": b"<p>new</p>"},
        deletes=["old.js", "never-existed.js"],
        message="feat(apps): update app from Nexus",
        author=ALICE,
        title="t",
        body="b",
    )

    tree_call = next(body for m, p, body in fake.calls if (m, p) == ("POST", "/git/trees"))
    assert tree_call["base_tree"] == "root-tree"
    assert tree_call["tree"] == [
        {"path": "src/app/index.html", "mode": "100644", "type": "blob", "sha": "blob-new"},
        {"path": "src/app/old.js", "mode": "100644", "type": "blob", "sha": None},
    ]
    blobs = [c for c in fake.calls if c[:2] == ("POST", "/git/blobs")]
    assert len(blobs) == 1  # same.css was not re-uploaded
    commit_call = next(body for m, p, body in fake.calls if (m, p) == ("POST", "/git/commits"))
    assert commit_call["parents"] == ["base-1"]
    assert commit_call["author"] == {"name": "Alice", "email": "alice@example.com"}
    ref_call = next(body for m, p, body in fake.calls if (m, p) == ("POST", "/git/refs"))
    assert ref_call == {"ref": "refs/heads/nexus-apps/ws-1/app", "sha": "commit-new"}
    assert submission.url == "https://github.com/org/bob/tree/nexus-apps/ws-1/app"
    assert submission.pull_request_url == "https://github.com/org/bob/pull/7"


def test_publish_moves_an_existing_review_branch_forward() -> None:
    publisher, fake = _publisher(
        _routes(
            {
                ("GET", "/git/ref/heads/nexus-apps/"): {"object": {"sha": "review-1"}},
                ("PATCH", "/git/refs/heads/nexus-apps/"): {"ref": "x"},
                ("GET", "/pulls"): [{"html_url": "https://github.com/org/bob/pull/3"}],
            }
        )
    )

    submission = publisher.publish(
        branch="nexus-apps/ws-1/app",
        target_path="src/app",
        writes={"index.html": b"<p>v2</p>"},
        deletes=[],
        message="m",
        author=ALICE,
        title="t",
        body="b",
    )

    commit_call = next(body for m, p, body in fake.calls if (m, p) == ("POST", "/git/commits"))
    assert commit_call["parents"] == ["review-1"]
    assert any(m == "PATCH" for m, _, _ in fake.calls)
    assert not any((m, p) == ("POST", "/pulls") for m, p, _ in fake.calls)
    assert submission.pull_request_url == "https://github.com/org/bob/pull/3"


def test_publish_with_nothing_changed_is_refused() -> None:
    publisher, _ = _publisher(_routes())
    with pytest.raises(AppProjectError, match="Nothing to submit"):
        publisher.publish(
            branch="nexus-apps/ws-1/app",
            target_path="src/app",
            writes={"same.css": b"same"},
            deletes=[],
            message="m",
            author=ALICE,
            title="t",
            body="b",
        )
