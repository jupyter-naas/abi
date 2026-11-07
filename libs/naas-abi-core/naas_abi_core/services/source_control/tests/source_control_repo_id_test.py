"""A repository's owner and name are plain path segments, whoever asks: the
local adapter makes directories of them and the forge puts them in URLs."""

from __future__ import annotations

import pytest
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    RepoNotFoundError,
    ValidationError,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

BAD = ["..", ".", "", "a/b", "../x", "x/..", "-x", ".hidden", "a b", "a\\b", "a\x00b"]


@pytest.fixture
def service(tmp_path):
    root = tmp_path / "repos"
    return SourceControlService(LocalGitAdapter(repos_root=str(root))), root


@pytest.mark.parametrize("bad", BAD)
def test_a_repository_owner_or_name_that_is_not_a_segment_creates_nothing(
    service, tmp_path, bad
):
    svc, root = service
    for call in (svc.ensure_repo, svc.create_repo):
        with pytest.raises(ValidationError):
            call(owner=bad, name="repo")
        with pytest.raises(ValidationError):
            call(owner="owner", name=bad)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["repos"]
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("bad", ["../outside/x", "owner/../../x", "a/b/c", "/etc/x"])
def test_a_repository_id_that_escapes_is_not_found_and_deletes_nothing(
    service, tmp_path, bad
):
    svc, _ = service
    victim = tmp_path / "outside" / "x"
    victim.mkdir(parents=True)
    (victim / "keep").write_text("data")
    with pytest.raises(RepoNotFoundError):
        svc.delete_repo(repo_id=bad)
    with pytest.raises(RepoNotFoundError):
        svc.list_branches(repo_id=bad)
    assert (victim / "keep").read_text() == "data"


def test_ordinary_names_still_work(service):
    svc, root = service
    repo = svc.create_repo(owner="acme-corp", name="my_repo.v2")
    assert (root / "acme-corp" / "my_repo.v2").is_dir()
    assert repo.name == "my_repo.v2"
    svc.delete_repo(repo_id="acme-corp/my_repo.v2")
