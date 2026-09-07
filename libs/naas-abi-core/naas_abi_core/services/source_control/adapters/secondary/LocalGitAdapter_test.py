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


def test_create_branch_conflict(adapter: LocalGitAdapter) -> None:
    repo = adapter.ensure_repo(owner="abi", name="demo")
    repo_id = f"{repo.owner}/{repo.name}"
    adapter.create_branch(repo_id=repo_id, name="feat/x", from_ref="main")
    with pytest.raises(BranchNameConflictError):
        adapter.create_branch(repo_id=repo_id, name="feat/x", from_ref="main")


def test_missing_repo(adapter: LocalGitAdapter) -> None:
    with pytest.raises(RepoNotFoundError):
        adapter.list_branches(repo_id="abi/missing")
