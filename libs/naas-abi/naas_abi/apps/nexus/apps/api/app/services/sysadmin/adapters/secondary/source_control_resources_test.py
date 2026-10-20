import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.source_control_resources import (
    SourceControlResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    FileWrite,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

REPO = "acme/project"


def _seed(service: SourceControlService, *, nested: bool) -> SourceControlService:
    service.ensure_repo(owner="acme", name="project")
    files = [FileWrite(path=k, content=v) for k, v in fixtures.SEED_ITEMS.items()]
    if nested:
        files += [
            FileWrite(path=f"{fixtures.SEED_CONTAINER}/{k}", content=v)
            for k, v in fixtures.SEED_NESTED.items()
        ]
    # The seed is exactly what the contract expects: drop the initial README.
    files.append(FileWrite(path="README.md", content=b"", delete=True))
    service.upsert_files(repo_id=REPO, files=files, message="seed", branch="main")
    return service


def _local(tmp_path) -> SourceControlService:
    return SourceControlService(LocalGitAdapter(repos_root=str(tmp_path / "git")))


class TestSourceControlResourcesOnLocalGit(ServiceResourcesContract):
    base = REPO
    containers = True

    @pytest.fixture
    def resources(self, tmp_path):
        return SourceControlResources(_seed(_local(tmp_path), nested=True))


class TestSourceControlResourcesOnAFlatBackend(ServiceResourcesContract):
    """The in-memory forge has no folders: every file sits at the repo root."""

    base = REPO

    @pytest.fixture
    def resources(self):
        return SourceControlResources(_seed(SourceControlService(InMemoryAdapter()), nested=False))


@pytest.fixture
def local(tmp_path):
    service = _seed(_local(tmp_path), nested=True)
    service.ensure_repo(owner="acme", name="docs")
    service.ensure_repo(owner="zeta", name="tools")
    return service


def run(coro):
    return asyncio.run(coro)


def test_root_lists_owners_then_repositories(local):
    resources = SourceControlResources(local)

    owners = run(resources.list("")).entries
    repos = run(resources.list("acme")).entries

    assert [(e.id, e.kind) for e in owners] == [("acme", "container"), ("zeta", "container")]
    assert [(e.id, e.actions) for e in repos] == [
        ("acme/docs", ("delete",)),
        ("acme/project", ("delete",)),
    ]
    assert repos[1].attributes["default_branch"] == "main"


def test_writes_are_commits_naming_the_system_app(local):
    resources = SourceControlResources(local)

    run(resources.write("acme/project/notes/todo.md", b"- ship it\n"))
    run(resources.write("acme/project/notes/todo.md", b"- shipped\n"))
    run(resources.delete("acme/project/alpha"))

    commits = local.list_commits(repo_id=REPO, limit=3)
    assert [c.message for c in commits] == [
        "Delete alpha from the Nexus System app",
        "Update notes/todo.md from the Nexus System app",
        "Create notes/todo.md from the Nexus System app",
    ]
    assert {c.author for c in commits} == {"Nexus System app"}
    (todo,) = run(resources.list("acme/project/notes")).entries
    assert run(resources.read(todo.id)).content.text == "- shipped\n"


def test_deleting_a_repository_removes_it_and_its_empty_owner(local):
    resources = SourceControlResources(local)

    run(resources.delete("zeta/tools"))

    assert [e.id for e in run(resources.list("")).entries] == ["acme"]
    with pytest.raises(ResourceNotFound):
        run(resources.stat("zeta/tools"))


def test_binary_files_download_exactly_and_preview_as_binary(local):
    resources = SourceControlResources(local)
    png = b"\x89PNG\r\n\x1a\n\x00\xff"

    run(resources.write("acme/project/logo.png", png))

    assert run(resources.download("acme/project/logo.png", max_bytes=100)) == png
    assert run(resources.read("acme/project/logo.png")).content.encoding == "binary"


@pytest.mark.parametrize(
    "bad", ["acme/project/../x", "/acme", "acme//project", "acme/project/a\\b"]
)
def test_malformed_paths_are_rejected(local, bad):
    with pytest.raises(InvalidResource):
        run(SourceControlResources(local).write(bad, b"x"))


def test_only_files_are_written_and_folders_are_not_deleted(local):
    resources = SourceControlResources(local)

    with pytest.raises(InvalidResource):
        run(resources.write("acme/project", b"x"))
    with pytest.raises(InvalidResource):
        run(resources.write("acme/project/nested", b"x"))
    with pytest.raises(UnsupportedOperation):
        run(resources.delete("acme/project/nested"))
    with pytest.raises(ResourceNotFound):
        run(resources.write("acme/missing/a.txt", b"x"))


def test_unknown_owners_and_repositories_are_not_found(local):
    resources = SourceControlResources(local)

    for missing in ("nobody", "acme/missing", "acme/missing/a.txt"):
        with pytest.raises(ResourceNotFound):
            run(resources.stat(missing))
    with pytest.raises(ResourceNotFound):
        run(resources.list("nobody"))


class _ForgeWithout(SourceControlService):
    """A backend that cannot delete repositories and denies listing contents."""

    def delete_repo(self, *, repo_id):
        raise NotImplementedError("delete_repo is not supported by this forge")

    def list_contents(self, *, repo_id, path="", ref=None):
        raise AccessDeniedError("token lacks repo scope", status=403)


def test_backend_limits_map_to_unsupported_and_unavailable(tmp_path):
    service = _ForgeWithout(InMemoryAdapter())
    service.ensure_repo(owner="acme", name="project")
    resources = SourceControlResources(service)

    with pytest.raises(UnsupportedOperation):
        run(resources.delete("acme/project"))
    with pytest.raises(SourceUnavailable) as exc:
        run(resources.list("acme/project"))
    assert "access denied" in exc.value.reason


def test_owners_and_repositories_carry_counts_and_visibility(local):
    resources = SourceControlResources(local)

    owners = {e.id: e for e in run(resources.list("")).entries}
    repos = {e.id: e for e in run(resources.list("acme")).entries}

    assert owners["acme"].attributes == {"repositories": "2", "summary": "2 repositories"}
    assert owners["zeta"].attributes["summary"] == "1 repository"
    project = repos["acme/project"].attributes
    assert project["visibility"] in ("private", "public")
    assert project["empty"] == "no"
    assert project["summary"].startswith("main · ")


def test_search_filters_each_level_by_name(local):
    resources = SourceControlResources(local)

    assert resources.capabilities.search is True
    assert [e.id for e in run(resources.list("", query="ZET")).entries] == ["zeta"]
    assert [e.id for e in run(resources.list("acme", query="doc")).entries] == ["acme/docs"]
    assert [e.name for e in run(resources.list("acme/project", query="ALP")).entries] == ["alpha"]


def test_folders_are_listed_before_files(local):
    local.upsert_files(
        repo_id=REPO, files=[FileWrite(path="aaa.txt", content=b"x")], message="m", branch="main"
    )

    names = [e.name for e in run(SourceControlResources(local).list(REPO)).entries]

    assert names[0] == fixtures.SEED_CONTAINER
    assert names[1:] == sorted(names[1:])
