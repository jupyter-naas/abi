from __future__ import annotations

import pytest
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    RepoNotFoundError,
)
from naas_abi_core.services.source_control.tests.source_control__secondary_adapter__generic_test import (
    GenericSourceControlSecondaryAdapterTest,
)


class TestLocalGitAdapter(GenericSourceControlSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return LocalGitAdapter


@pytest.fixture
def adapter(tmp_path):
    return LocalGitAdapter(repos_root=str(tmp_path / "git"))


def test_ensure_repo_and_list_contents(adapter: LocalGitAdapter) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    entries = adapter.list_contents(repo_id=repo_id)
    assert any(entry.name == "README.md" for entry in entries)
    file = adapter.get_file(repo_id=repo_id, path="README.md")
    assert file.text is not None
    assert "demo" in file.text


def _seed_deck(adapter: LocalGitAdapter, repo_id: str, root: str) -> None:
    for name, content in (("deck.html", "<html></html>\n"), ("project.json", "{}\n")):
        adapter.upsert_file(
            repo_id=repo_id,
            path=f"{root}/{name}",
            content=content,
            message=f"add {name}",
            branch="main",
        )


def test_list_contents_returns_what_is_inside_a_directory(
    adapter: LocalGitAdapter,
) -> None:
    """``git ls-tree <ref> <dir>`` without a trailing slash reports the
    directory entry itself, so a deck folder came back as its own child and
    the files next to ``deck.html`` were never listed.
    """
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    root = "slides/ws-demo/deck-one"
    _seed_deck(adapter, repo_id, root)

    entries = adapter.list_contents(repo_id=repo_id, path=root)

    assert [entry.name for entry in entries] == ["deck.html", "project.json"]
    assert [entry.path for entry in entries] == [
        f"{root}/deck.html",
        f"{root}/project.json",
    ]
    assert {entry.type for entry in entries} == {"file"}


def test_list_contents_treats_a_trailing_slash_as_the_same_directory(
    adapter: LocalGitAdapter,
) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    root = "slides/ws-demo/deck-one"
    _seed_deck(adapter, repo_id, root)

    plain = adapter.list_contents(repo_id=repo_id, path=root)
    slashed = adapter.list_contents(repo_id=repo_id, path=f"{root}/")

    assert [entry.path for entry in slashed] == [entry.path for entry in plain]


def test_list_contents_lists_the_repo_root_without_the_root_itself(
    adapter: LocalGitAdapter,
) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    _seed_deck(adapter, repo_id, "slides/ws-demo/deck-one")

    for root_path in ("", "/"):
        entries = adapter.list_contents(repo_id=repo_id, path=root_path)
        assert [entry.name for entry in entries] == ["README.md", "slides"]
        assert [entry.type for entry in entries] == ["file", "dir"]


def test_list_contents_is_empty_for_a_path_that_does_not_exist(
    adapter: LocalGitAdapter,
) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    _seed_deck(adapter, repo_id, "slides/ws-demo/deck-one")

    assert adapter.list_contents(repo_id=repo_id, path="slides/ws-demo/nope") == []


def test_list_contents_of_a_directory_holding_only_a_placeholder(
    adapter: LocalGitAdapter,
) -> None:
    """Git has no empty trees, so the nearest thing a deck can have is an
    assets folder seeded with a single placeholder file.
    """
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    root = "slides/ws-demo/deck-one"
    adapter.upsert_file(
        repo_id=repo_id,
        path=f"{root}/assets/.gitkeep",
        content="",
        message="seed assets",
        branch="main",
    )

    entries = adapter.list_contents(repo_id=repo_id, path=f"{root}/assets")

    assert [entry.name for entry in entries] == [".gitkeep"]


def test_branch_and_commit_flow(adapter: LocalGitAdapter) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    adapter.create_branch(repo_id=repo_id, name="feat/x", from_ref="main")
    adapter.upsert_file(
        repo_id=repo_id,
        path="notes.txt",
        content="hello\n",
        message="add notes",
        branch="feat/x",
    )
    commits = adapter.list_commits(repo_id=repo_id, ref="feat/x", limit=5)
    assert commits
    assert commits[0].message == "add notes"


def test_list_commits_when_branch_name_shadows_a_real_path(
    adapter: LocalGitAdapter,
) -> None:
    """Slides branches are ``slides/<ws>/<slug>`` and the deck lives at the
    same path, so ``git log <ref>`` without ``--`` is ambiguous.
    """
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    branch = "slides/ws-demo/quarterly-review"
    adapter.create_branch(repo_id=repo_id, name=branch, from_ref="main")
    adapter.upsert_file(
        repo_id=repo_id,
        path=f"{branch}/deck.html",
        content="<html></html>\n",
        message="add deck",
        branch=branch,
    )
    commits = adapter.list_commits(repo_id=repo_id, ref=branch, limit=5)
    assert commits
    assert commits[0].message == "add deck"


def test_create_branch_conflict(adapter: LocalGitAdapter) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    adapter.create_branch(repo_id=repo_id, name="feat/x", from_ref="main")
    with pytest.raises(BranchNameConflictError):
        adapter.create_branch(repo_id=repo_id, name="feat/x", from_ref="main")


def test_missing_repo(adapter: LocalGitAdapter) -> None:
    with pytest.raises(RepoNotFoundError):
        adapter.list_branches(repo_id="abi/missing")
