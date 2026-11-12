"""Every source control request stays inside the repository it names.

File paths, branches, refs, commits and usernames are names inside one
repository: the service refuses one that could name something else, for every
adapter, and each adapter keeps what it builds from them (an API URL, a file
path, a git argument) inside that repository.
"""

from __future__ import annotations

import os
import posixpath
import stat
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest
import requests
from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
    ForgejoAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)
from naas_abi_core.services.source_control.names import (
    commit_ok,
    file_path_ok,
    ref_ok,
    username_ok,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    FileWrite,
    SourceControlError,
    ValidationError,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

OUTSIDE_PATHS = [
    "../../../other/repo/contents/x",
    "../x",
    "a/../../x",
    "./x",
    "a//b",
    ".git/config",
    "a/.GIT/hooks/pre-commit",
    "x?ref=other",
    "x#fragment",
    "a\\..\\b",
    "a\x00b",
    "a\nb",
]
OUTSIDE_REFS = [
    "../../../other/repo",
    "-x",
    "--output=/tmp/x",
    "a..b",
    "a b",
    "x#y",
    "x?y",
    "a/./b",
    "a//b",
    "/main",
    "main/",
    "main.lock",
    "HEAD~1",
    "main^",
    "a:b",
    "@",
    "a@{1}",
    ".hidden",
    "a\x01b",
]
OUTSIDE_COMMITS = ["main", "x/../../admin/users#", "-x", "abc", "g" * 40, ""]
OUTSIDE_USERNAMES = ["../admin", "a/b", "-x", ".x", "a b", "a..b", "", "a#b"]

ORDINARY_PATHS = ["README.md", "/docs/a b.md", "dir/sub/", "naïve/ü.txt", ".forgejo/x.yml"]
ORDINARY_REFS = ["main", "feature/x", "release/1.0", "slides/ws-1/deck", "0" * 40]


# -- the names ----------------------------------------------------------------


@pytest.mark.parametrize("path", OUTSIDE_PATHS)
def test_a_file_path_keeps_inside_the_tree(path: str) -> None:
    assert not file_path_ok(path)
    assert not file_path_ok(path, root_ok=True)


@pytest.mark.parametrize("path", ORDINARY_PATHS)
def test_ordinary_file_paths_are_kept(path: str) -> None:
    assert file_path_ok(path)


@pytest.mark.parametrize("ref", OUTSIDE_REFS)
def test_a_ref_keeps_to_one_name(ref: str) -> None:
    assert not ref_ok(ref)


@pytest.mark.parametrize("ref", ORDINARY_REFS)
def test_ordinary_refs_are_kept(ref: str) -> None:
    assert ref_ok(ref)


@pytest.mark.parametrize("sha", OUTSIDE_COMMITS)
def test_a_diff_base_keeps_to_a_commit_id(sha: str) -> None:
    assert not commit_ok(sha)


@pytest.mark.parametrize("username", OUTSIDE_USERNAMES)
def test_a_username_keeps_to_one_segment(username: str) -> None:
    assert not username_ok(username)


# -- the service, for every adapter ---------------------------------------------


@pytest.fixture
def service() -> SourceControlService:
    svc = SourceControlService(InMemoryAdapter())
    svc.ensure_repo(owner="atk", name="mine")
    return svc


def _calls_with(
    svc: SourceControlService, *, path: str = "README.md", ref: str = "main"
) -> list:
    repo = "atk/mine"
    return [
        lambda: svc.get_file(repo_id=repo, path=path, ref=ref),
        lambda: svc.list_contents(repo_id=repo, path=path, ref=ref),
        lambda: svc.upsert_file(
            repo_id=repo, path=path, content="x", message="m", branch=ref
        ),
        lambda: svc.upsert_files(
            repo_id=repo, files=[FileWrite(path, b"x")], message="m", branch=ref
        ),
        lambda: svc.list_commits(repo_id=repo, ref=ref),
        lambda: svc.create_branch(repo_id=repo, name=ref, from_ref="main"),
        lambda: svc.create_branch(repo_id=repo, name="feature/new", from_ref=ref),
        lambda: svc.delete_branch(repo_id=repo, name=ref),
    ]


@pytest.mark.parametrize("path", OUTSIDE_PATHS)
def test_the_service_keeps_file_paths_inside_the_repository(
    service: SourceControlService, path: str
) -> None:
    for call in _calls_with(service, path=path)[:4]:
        with pytest.raises(ValidationError):
            call()


@pytest.mark.parametrize("ref", OUTSIDE_REFS)
def test_the_service_keeps_branches_and_refs_inside_the_repository(
    service: SourceControlService, ref: str
) -> None:
    for call in _calls_with(service, ref=ref):
        with pytest.raises(ValidationError):
            call()


@pytest.mark.parametrize("sha", OUTSIDE_COMMITS)
def test_the_service_keeps_diffs_to_commit_ids(
    service: SourceControlService, sha: str
) -> None:
    with pytest.raises(ValidationError):
        service.get_diff(repo_id="atk/mine", base=sha, head="0" * 40)
    with pytest.raises(ValidationError):
        service.get_diff(repo_id="atk/mine", base="0" * 40, head=sha)


@pytest.mark.parametrize("username", OUTSIDE_USERNAMES)
def test_the_service_keeps_usernames_to_one_segment(
    service: SourceControlService, username: str
) -> None:
    with pytest.raises(ValidationError):
        service.add_collaborator(repo_id="atk/mine", username=username)
    with pytest.raises(ValidationError):
        service.ensure_user(email="a@example.com", username=username)
    if username:  # no user at all is the owner's to fill, behind a facade
        with pytest.raises(ValidationError):
            service.mint_git_token(user_id=username)


def test_the_service_keeps_ordinary_names_working(service: SourceControlService) -> None:
    service.create_branch(repo_id="atk/mine", name="feature/x", from_ref="main")
    service.upsert_file(
        repo_id="atk/mine",
        path="docs/a b.md",
        content="x",
        message="m",
        branch="feature/x",
    )
    assert service.get_file(repo_id="atk/mine", path="docs/a b.md", ref="feature/x")
    service.delete_branch(repo_id="atk/mine", name="feature/x")


# -- the Forgejo adapter --------------------------------------------------------


class _Response:
    status_code = 200
    content = b"{}"
    text = "{}"

    def json(self) -> dict:
        return {}


class _RecordingSession:
    """Records the path each request would really reach: ``requests``
    normalizes dot segments before sending, as a live session does."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.bodies: list = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        prepared = requests.Request(method, url).prepare()
        self.sent.append((method, prepared.path_url))
        self.bodies.append(json)
        return _Response()


REPO_PREFIX = "/api/v1/repos/atk/mine"


def _forgejo() -> tuple[ForgejoAdapter, _RecordingSession]:
    session = _RecordingSession()
    adapter = ForgejoAdapter(
        base_url="http://forgejo.invalid", admin_token="token", session=session
    )
    return adapter, session


def _stays_in_repository(path_url: str) -> bool:
    route = path_url.split("?", 1)[0]
    return posixpath.normpath(route).startswith(f"{REPO_PREFIX}/") or route == REPO_PREFIX


def _repo_calls(adapter: ForgejoAdapter, value: str) -> list:
    repo = "atk/mine"
    return [
        lambda: adapter.get_file(repo_id=repo, path=value),
        lambda: adapter.list_contents(repo_id=repo, path=value),
        lambda: adapter.upsert_file(
            repo_id=repo, path=value, content="x", message="m", branch="main"
        ),
        lambda: adapter.upsert_files(
            repo_id=repo,
            files=[FileWrite(value, b"x"), FileWrite("other", b"y")],
            message="m",
            branch="main",
        ),
        lambda: adapter.delete_branch(repo_id=repo, name=value),
        lambda: adapter.add_collaborator(repo_id=repo, username=value),
        lambda: adapter.get_diff(repo_id=repo, base=value, head="0" * 40),
        lambda: adapter.get_diff(repo_id=repo, base="0" * 40, head=value),
    ]


@pytest.mark.parametrize(
    "value",
    [
        *OUTSIDE_PATHS,
        *OUTSIDE_REFS,
        "x/../../../../../admin/users#",
        "../../../victim/secret/collaborators/mallory",
        "%2e%2e/%2e%2e/victim",
    ],
)
def test_forgejo_requests_keep_inside_their_repository(value: str) -> None:
    """Whatever the adapter is handed, every request about a repository it
    sends stays under ``/api/v1/repos/{owner}/{name}/``: a name it cannot
    encode as one is refused before anything is sent."""
    adapter, session = _forgejo()
    for call in _repo_calls(adapter, value):
        try:
            call()
        except SourceControlError:
            pass
    assert session.sent, "nothing to check"
    outside = [sent for sent in session.sent if not _stays_in_repository(sent[1])]
    assert outside == []


@pytest.mark.parametrize("path", ["docs/a b.md", "naïve/ü#1?.md", "a+b@c:d.md"])
def test_forgejo_encodes_each_segment_of_a_file_path(path: str) -> None:
    adapter, session = _forgejo()
    adapter.get_file(repo_id="atk/mine", path=path, ref="feature/x")
    _, sent = session.sent[-1]
    route, _, query = sent.partition("?")
    assert route.startswith(f"{REPO_PREFIX}/contents/")
    assert [unquote(part) for part in route.split("/")[7:]] == path.split("/")
    assert query == "ref=feature%2Fx"


def test_forgejo_keeps_a_branch_with_slashes_as_one_name() -> None:
    adapter, session = _forgejo()
    adapter.delete_branch(repo_id="atk/mine", name="feature/a b")
    assert session.sent == [("DELETE", f"{REPO_PREFIX}/branches/feature/a%20b")]


def test_forgejo_encodes_usernames() -> None:
    adapter, session = _forgejo()
    adapter.add_collaborator(repo_id="atk/mine", username="a/../b")
    assert session.sent == [("PUT", f"{REPO_PREFIX}/collaborators/a%2F..%2Fb")]

    adapter, session = _forgejo()
    adapter.mint_git_token(user_id="a/../b")
    assert ("POST", "/api/v1/users/a%2F..%2Fb/tokens") in session.sent
    for _, sent in session.sent:
        route = sent.split("?", 1)[0]
        assert "/a%2F..%2Fb" in route or route == "/api/v1/admin/users"
    with pytest.raises(ValidationError):
        adapter.mint_git_token(user_id="")


def test_forgejo_batch_writes_keep_empty_paths_out() -> None:
    adapter, session = _forgejo()
    adapter.upsert_files(
        repo_id="atk/mine",
        files=[FileWrite("", b"x"), FileWrite("/", b"x"), FileWrite("a.md", b"y")],
        message="m",
        branch="main",
    )
    batch = [
        body
        for (method, sent), body in zip(session.sent, session.bodies, strict=True)
        if method == "POST" and sent == f"{REPO_PREFIX}/contents"
    ]
    assert [op["path"] for op in batch[0]["files"]] == ["a.md"]
    assert all(
        sent.split("?", 1)[0] != f"{REPO_PREFIX}/contents/" for _, sent in session.sent
    )


# -- the local git adapter ------------------------------------------------------


@pytest.fixture
def local(tmp_path: Path) -> tuple[LocalGitAdapter, Path]:
    root = tmp_path / "repos"
    adapter = LocalGitAdapter(repos_root=str(root))
    adapter.ensure_repo(owner="atk", name="mine")
    adapter.ensure_repo(owner="victim", name="secret")
    return adapter, root


def _snapshot(base: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(base)): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize(
    "path",
    [
        "../../victim/secret/planted",
        "../../../outside",
        ".git/config",
        "a/../../../victim/secret/x",
        ".GIT/hooks/post-commit",
    ],
)
def test_local_git_writes_keep_inside_the_repository(
    local: tuple[LocalGitAdapter, Path], path: str
) -> None:
    adapter, root = local
    before = _snapshot(root.parent)
    for svc_or_adapter in (SourceControlService(adapter), adapter):
        with pytest.raises(ValidationError):
            svc_or_adapter.upsert_file(
                repo_id="atk/mine", path=path, content="x", message="m", branch="main"
            )
        with pytest.raises(ValidationError):
            svc_or_adapter.upsert_files(
                repo_id="atk/mine",
                files=[FileWrite(path, b"x")],
                message="m",
                branch="main",
            )
    assert _snapshot(root.parent) == before


def test_local_git_writes_keep_out_of_symbolic_links(
    local: tuple[LocalGitAdapter, Path], tmp_path: Path
) -> None:
    adapter, root = local
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = root / "atk" / "mine"
    os.symlink(outside, repo / "link")
    with pytest.raises(ValidationError):
        adapter.upsert_file(
            repo_id="atk/mine", path="link/x", content="x", message="m", branch="main"
        )
    assert list(outside.iterdir()) == []


def test_local_git_keeps_repository_hooks_and_fsmonitor_off(
    local: tuple[LocalGitAdapter, Path], tmp_path: Path
) -> None:
    adapter, root = local
    repo = root / "atk" / "mine"
    marker = tmp_path / "ran"
    script = tmp_path / "hook.sh"
    script.write_text(f"#!/bin/sh\necho ran >> {marker}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    for hook in ("pre-commit", "post-commit", "post-checkout"):
        target = repo / ".git" / "hooks" / hook
        target.write_bytes(script.read_bytes())
        target.chmod(script.stat().st_mode)
    subprocess.run(
        ["git", "config", "core.fsmonitor", str(script)], cwd=repo, check=True
    )
    adapter.upsert_file(
        repo_id="atk/mine", path="docs/x.md", content="x", message="m", branch="main"
    )
    adapter.create_branch(repo_id="atk/mine", name="feature/x", from_ref="main")
    adapter.upsert_file(
        repo_id="atk/mine", path="docs/y.md", content="y", message="m", branch="feature/x"
    )
    assert not marker.exists()


@pytest.mark.parametrize("ref", ["--output=OUT", "-x", "--all"])
def test_local_git_keeps_refs_from_being_options(
    local: tuple[LocalGitAdapter, Path], tmp_path: Path, ref: str
) -> None:
    adapter, _ = local
    written = tmp_path / "out"
    ref = ref.replace("OUT", str(written))
    calls = [
        lambda: adapter.list_commits(repo_id="atk/mine", ref=ref),
        lambda: adapter.get_file(repo_id="atk/mine", path="README.md", ref=ref),
        lambda: adapter.list_contents(repo_id="atk/mine", ref=ref),
        lambda: adapter.create_branch(repo_id="atk/mine", name=ref, from_ref="main"),
        lambda: adapter.create_branch(repo_id="atk/mine", name="b", from_ref=ref),
        lambda: adapter.upsert_file(
            repo_id="atk/mine", path="x", content="x", message="m", branch=ref
        ),
    ]
    for call in calls:
        with pytest.raises(ValidationError):
            call()
    assert not written.exists()


def test_local_git_reads_keep_inside_the_repository(
    local: tuple[LocalGitAdapter, Path],
) -> None:
    adapter, _ = local
    for path in ("../../victim/secret/README.md", ".git/config"):
        with pytest.raises(ValidationError):
            adapter.get_file(repo_id="atk/mine", path=path)
        with pytest.raises(ValidationError):
            adapter.list_contents(repo_id="atk/mine", path=path)
    readme = adapter.get_file(repo_id="atk/mine", path="/README.md")
    assert (readme.text or "").startswith("# mine")


def test_local_git_listing_keeps_to_the_directory_asked_for(
    local: tuple[LocalGitAdapter, Path],
) -> None:
    adapter, _ = local
    adapter.upsert_files(
        repo_id="atk/mine",
        files=[FileWrite("--", b"x"), FileWrite("d/x", b"y")],
        message="m",
        branch="main",
    )
    listed = adapter.list_contents(repo_id="atk/mine", path="d")
    assert [entry.path for entry in listed] == ["d/x"]
