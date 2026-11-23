from __future__ import annotations

import json
import stat
import subprocess
import urllib.request
from pathlib import Path

import pytest
from naas_abi_core.services.coding_environment.adapters.secondary.LocalDirectoryAdapter import (
    LocalDirectoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    InvalidRequestError,
    ProvisionFailedError,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
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
    adapter = LocalDirectoryAdapter(
        workspaces_root=str(tmp_path / "workspaces"),
        single_user_development=True,
        repos_root=str(tmp_path / "git"),
    )
    yield adapter
    # Provisioning starts a sidecar process; it outlives the test otherwise.
    for environment in adapter.list_all_environments():
        adapter.stop(workspace_id=environment.id)


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

    adapter = LocalDirectoryAdapter(workspaces_root=str(root), single_user_development=True)
    environments = {e.id: e for e in adapter.list_all_environments()}

    assert set(environments) == {"w1", "w2"}
    assert environments["w2"].owner == "u-bob"
    assert environments["w1"].template == LocalDirectoryAdapter.TEMPLATE_ID
    assert environments["w1"].created_at == "2026-10-02T10:00:00+00:00"
    assert [e.id for e in adapter.list_environments(user_id="u-alice")] == ["w1"]


# -- the runtime stays the user's, off the engine's secrets and files ----------


def _provision(adapter: LocalDirectoryAdapter, user_id: str = "user-1", **kw):
    return adapter.provision(
        user_id=user_id,
        template_id=LocalDirectoryAdapter.TEMPLATE_ID,
        name=kw.pop("name", "dev"),
        params=kw.pop("params", None),
    )


def _terminal(adapter: LocalDirectoryAdapter, workspace_id: str, command: str) -> dict:
    binding = adapter.get_runtime_binding(workspace_id=workspace_id)
    assert binding is not None
    base, secret = binding
    request = urllib.request.Request(
        f"{base}/tools/run_terminal",
        data=json.dumps({"command": command}).encode(),
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
        return json.loads(response.read())


def test_local_directory_keeps_the_engine_environment_from_its_runtime(
    workspace_adapter: LocalDirectoryAdapter, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ENGINE_ONLY_SECRET", "kept-by-the-engine")
    status = _provision(workspace_adapter)
    out = _terminal(workspace_adapter, status.id, "env")["stdout"]
    assert "kept-by-the-engine" not in out
    assert "ENGINE_ONLY_SECRET" not in out
    home = _terminal(workspace_adapter, status.id, 'printf %s "$HOME"')["stdout"]
    assert home != str(Path.home())
    assert Path(home).is_relative_to(tmp_path / "workspaces")


def test_local_directory_keeps_to_a_single_user(
    workspace_adapter: LocalDirectoryAdapter,
) -> None:
    _provision(workspace_adapter, "user-1")
    with pytest.raises(AccessDeniedError):
        _provision(workspace_adapter, "user-2", name="other")
    assert [e.owner for e in workspace_adapter.list_all_environments()] == ["user-1"]


@pytest.mark.parametrize("name", ["/abs/path", "../user-2/dev", "a/b", "..", "Dev", ".home"])
def test_local_directory_keeps_checkouts_under_the_users_root(
    workspace_adapter: LocalDirectoryAdapter, tmp_path, name: str
) -> None:
    outside = tmp_path / "engine-data"
    outside.mkdir()
    (outside / "keep.txt").write_text("engine data")
    for provision in (
        lambda: _provision(workspace_adapter, name=name),
        lambda: CodingEnvironmentService(workspace_adapter).provision(
            user_id="user-1", template_id=LocalDirectoryAdapter.TEMPLATE_ID, name=name
        ),
    ):
        with pytest.raises(InvalidRequestError):
            provision()
    assert (outside / "keep.txt").read_text() == "engine data"
    assert workspace_adapter.list_all_environments() == []


def test_local_directory_never_replaces_an_existing_directory(
    workspace_adapter: LocalDirectoryAdapter, tmp_path
) -> None:
    existing = tmp_path / "workspaces" / "user-1" / "dev"
    existing.mkdir(parents=True)
    (existing / "keep.txt").write_text("kept")
    with pytest.raises(ProvisionFailedError):
        _provision(workspace_adapter)
    assert (existing / "keep.txt").read_text() == "kept"


def test_local_directory_keeps_clones_to_the_platforms_forge(
    tmp_path, git_repo
) -> None:
    _, repo = git_repo
    adapter = LocalDirectoryAdapter(
        workspaces_root=str(tmp_path / "workspaces"),
        single_user_development=True,
        repos_root=str(tmp_path / "git"),
        forge_url="http://forge.internal:3000",
    )
    elsewhere = tmp_path / "elsewhere" / "abi" / "demo"
    subprocess.run(["git", "init", "-q", str(elsewhere)], check=True)
    refused = [
        str(elsewhere),
        elsewhere.as_uri(),
        str(tmp_path / "git" / "abi" / "demo"),  # a path, not the forge's URL
        (tmp_path / "git" / "abi").as_uri(),
        (tmp_path / "git" / "abi" / "demo" / ".." / "demo").as_uri() + "/../../x",
        "http://127.0.0.1:9/abi/demo.git",
        "https://forge.internal:3000/abi/demo.git",
        "http://forge.internal:3000/abi/demo/extra.git",
        "http://forge.internal:3000/abi/demo.git?x=1",
        "ssh://forge.internal/abi/demo.git",
        "--upload-pack=touch /tmp/x",
        "ext::sh -c touch% /tmp/x",
    ]
    try:
        for url in refused:
            with pytest.raises(InvalidRequestError):
                _provision(adapter, params={"repo_url": url})
        assert adapter.list_all_environments() == []
        # The forge's own repository is cloned.
        status = _provision(adapter, params={"repo_url": repo.clone_url, "branch": "main"})
        assert status.phase == "running"
    finally:
        for environment in adapter.list_all_environments():
            adapter.stop(workspace_id=environment.id)


def test_local_directory_harness_keeps_its_own_environment_and_credentials(
    tmp_path, monkeypatch
) -> None:
    from naas_abi_core.services.agent.OpencodeAgent import OpencodeAgent

    record = tmp_path / "harness.json"
    fake = tmp_path / "opencode"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, stat\n"
        "auth = os.path.join(os.environ['XDG_DATA_HOME'], 'opencode', 'auth.json')\n"
        "seen = {'env': dict(os.environ), 'cwd': os.getcwd(),\n"
        "        'auth': json.load(open(auth)),\n"
        "        'auth_mode': stat.S_IMODE(os.stat(auth).st_mode)}\n"
        f"json.dump(seen, open({str(record)!r}, 'w'))\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ENGINE_ONLY_SECRET", "kept-by-the-engine")
    monkeypatch.setattr(
        OpencodeAgent,
        "opencode_auth_data",
        classmethod(lambda cls: {"openai": {"type": "api", "key": "harness-key"}}),
    )
    adapter = LocalDirectoryAdapter(
        workspaces_root=str(tmp_path / "workspaces"),
        single_user_development=True,
        harness="opencode",
        opencode_bin=str(fake),
        opencode_startup_timeout=1,
    )
    with pytest.raises(ProvisionFailedError):  # the fake never serves
        _provision(adapter)
    seen = json.loads(record.read_text())
    assert "ENGINE_ONLY_SECRET" not in seen["env"]
    home = Path(seen["env"]["HOME"])
    assert home != Path.home()
    assert home.is_relative_to(tmp_path / "workspaces")
    assert seen["auth"] == {"openai": {"type": "api", "key": "harness-key"}}
    assert seen["auth_mode"] == 0o600
    # The provision failed: its home, with the credentials, is gone with it.
    assert not home.exists()
    assert not (tmp_path / "workspaces" / "user-1" / "dev").exists()


@pytest.mark.parametrize("failing", ["_allocate_sidecar_port", "_start_sidecar", "_persist"])
def test_local_directory_failed_provision_keeps_the_name_free(
    workspace_adapter: LocalDirectoryAdapter, tmp_path, monkeypatch, failing: str
) -> None:
    """Whatever step fails, the provision leaves no checkout and no home
    behind: the same name provisions again."""

    def fail(*_args, **_kwargs):
        raise OSError("no resource")

    with monkeypatch.context() as patch:
        patch.setattr(workspace_adapter, failing, fail)
        with pytest.raises(OSError):
            _provision(workspace_adapter)
    user_root = tmp_path / "workspaces" / "user-1"
    assert not (user_root / "dev").exists()
    assert not (user_root / ".home" / "dev").exists()
    assert workspace_adapter.list_all_environments() == []

    status = _provision(workspace_adapter)
    assert status.name == "dev"


def test_local_directory_harness_keeps_its_missing_credentials_visible(
    tmp_path, monkeypatch
) -> None:
    from naas_abi_core.services.agent import OpencodeAgent as opencode_module

    warned: list[str] = []
    monkeypatch.setattr(
        opencode_module.OpencodeAgent, "opencode_auth_data", classmethod(lambda cls: {})
    )
    monkeypatch.setattr(
        opencode_module, "warn_no_opencode_credentials", lambda: warned.append("x")
    )
    adapter = LocalDirectoryAdapter(
        workspaces_root=str(tmp_path / "workspaces"),
        single_user_development=True,
        harness="opencode",
        opencode_bin="true",
        opencode_startup_timeout=1,
    )
    with pytest.raises(ProvisionFailedError):
        _provision(adapter)
    assert warned == ["x"]
