from __future__ import annotations

import pytest
from naas_abi_core.services.coding_environment.adapters.secondary.LocalDirectoryAdapter import (
    LocalDirectoryAdapter,
)
from naas_abi_core.services.coding_environment.tests.coding_environment__secondary_adapter__generic_test import (
    GenericCodingEnvironmentSecondaryAdapterTest,
)
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)


class TestLocalDirectoryAdapter(GenericCodingEnvironmentSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return LocalDirectoryAdapter


@pytest.fixture
def git_repo(tmp_path):
    adapter = LocalGitAdapter(repos_root=str(tmp_path / "git"))
    repo = adapter.ensure_repo(owner="abi", name="demo")
    return adapter, repo


@pytest.fixture
def workspace_adapter(tmp_path):
    return LocalDirectoryAdapter(workspaces_root=str(tmp_path / "workspaces"))


def test_provision_clone_and_sidecar(
    workspace_adapter: LocalDirectoryAdapter, git_repo
) -> None:
    git_adapter, repo = git_repo
    user_id = "user-1"
    workspace_adapter.ensure_user(
        external_id=user_id, email="u@example.com", username="user"
    )
    status = workspace_adapter.provision(
        user_id=user_id,
        template_id=LocalDirectoryAdapter.TEMPLATE_ID,
        name="swift-otter",
        params={
            "repo_url": repo.clone_url,
            "branch": "main",
            "sidecar_secret": "test-secret",
        },
    )
    assert status.phase == "running"
    assert status.agent_ready
    binding = workspace_adapter.get_runtime_binding(workspace_id=status.id)
    assert binding is not None
    base, secret = binding
    assert base.startswith("http://127.0.0.1:")
    assert secret == "test-secret"
    logs = workspace_adapter.get_logs(workspace_id=status.id)
    assert any("sidecar:" in line for line in logs)
    del git_adapter


def test_list_all_environments_reads_every_persisted_workspace(tmp_path) -> None:
    import json

    root = tmp_path / "workspaces"
    for user, name, workspace_id in (("u-alice", "dev", "w1"), ("u-bob", "api", "w2")):
        meta = root / user / name / ".abi" / "workspace.json"
        meta.parent.mkdir(parents=True)
        meta.write_text(
            json.dumps(
                {
                    "id": workspace_id,
                    "name": name,
                    "user_id": user,
                    "checkout": str(root / user / name),
                    "phase": "stopped",
                    "created_at": "2026-10-02T10:00:00+00:00",
                }
            )
        )

    adapter = LocalDirectoryAdapter(workspaces_root=str(root))
    environments = {e.id: e for e in adapter.list_all_environments()}

    assert set(environments) == {"w1", "w2"}
    assert environments["w2"].owner == "u-bob"
    assert environments["w1"].template == LocalDirectoryAdapter.TEMPLATE_ID
    assert environments["w1"].created_at == "2026-10-02T10:00:00+00:00"
    assert [e.id for e in adapter.list_environments(user_id="u-alice")] == ["w1"]
