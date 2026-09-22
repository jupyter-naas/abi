"""Conditional writes must reject stale clients and actual racing writers."""

import base64
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
    ForgejoAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    FileWrite,
    RevisionConflictError,
    SourceControlError,
    content_revision,
)


@pytest.fixture(params=["local", "memory"])
def adapter(request, tmp_path):
    result = (
        LocalGitAdapter(repos_root=str(tmp_path))
        if request.param == "local"
        else InMemoryAdapter()
    )
    result.ensure_repo(owner="test", name="sheets")
    result.upsert_file(
        repo_id="test/sheets",
        path="workbook.html",
        content="original\n",
        message="seed",
        branch="main",
    )
    return result


def write(adapter, content):
    return adapter.compare_and_swap_file(
        repo_id="test/sheets",
        path="workbook.html",
        content=content,
        expected_revision=content_revision("original\n"),
        message="save",
        branch="main",
    )


def test_stale_revision_cannot_overwrite_and_metadata_preserves_workbook(adapter):
    write(adapter, "winner")
    with pytest.raises(RevisionConflictError):
        write(adapter, "stale")
    adapter.upsert_files(
        repo_id="test/sheets",
        files=[FileWrite(path="project.json", content="{}")],
        message="metadata",
        branch="main",
    )
    assert (
        adapter.get_file(repo_id="test/sheets", path="workbook.html", ref="main").text
        == "winner"
    )


def test_local_git_atomic_ref_rejects_race_after_both_read(tmp_path, monkeypatch):
    adapter = LocalGitAdapter(repos_root=str(tmp_path))
    adapter.ensure_repo(owner="test", name="sheets")
    adapter.upsert_file(
        repo_id="test/sheets",
        path="workbook.html",
        content="original\n",
        message="seed",
        branch="main",
    )
    barrier = Barrier(2)
    original = adapter._run

    def run(*args, **kwargs):
        if args[0] == "update-ref":
            barrier.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_run", run)

    def attempt(content):
        try:
            write(adapter, content)
            return content
        except RevisionConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["first", "second"]))
    winners = [item for item in results if item]
    assert len(winners) == 1
    assert (
        adapter.get_file(repo_id="test/sheets", path="workbook.html", ref="main").text
        == winners[0]
    )


def test_forgejo_passes_original_blob_sha_and_never_retries_conflict(monkeypatch):
    adapter = ForgejoAdapter(base_url="https://forge.example", admin_token="test")
    calls = []

    def request(method, path, **kwargs):
        calls.append(method)
        if method == "GET":
            return {
                "sha": "original-blob",
                "content": base64.b64encode(b"original\n").decode(),
            }
        assert kwargs["json"]["sha"] == "original-blob"
        raise SourceControlError("sha does not match")

    monkeypatch.setattr(adapter, "_request", request)
    with pytest.raises(RevisionConflictError):
        write(adapter, "stale")
    assert calls == ["GET", "PUT"]
