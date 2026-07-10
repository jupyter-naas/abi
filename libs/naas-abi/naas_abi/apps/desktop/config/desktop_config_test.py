"""Unit tests for desktop_config filesystem helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop.config import desktop_config
from desktop.config.desktop_config import (
    BUNDLED_ONTOLOGY_DIR,
    COMMON_API_KEYS,
    add_recent_workspace,
    build_shell_env_source,
    merged_env_keys,
    parse_recent_workspaces,
    resolve_env_files,
    resolve_system_ontology_paths,
    serialize_recent_workspaces,
    workspace_display_name,
    workspace_env_report,
)


def test_ensure_workspace_creates_dir_and_git_inits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"cmd": cmd, **kwargs})
        (Path(kwargs["cwd"]) / ".git").mkdir()

    monkeypatch.setattr("subprocess.run", fake_run)
    workspace = tmp_path / "workspace"
    desktop_config.ensure_workspace(workspace)

    assert workspace.is_dir()
    assert (workspace / "opencode.json").is_file()
    assert (workspace / ".env.example").is_file()
    assert (workspace / "desktop.md").is_file()
    assert (workspace / "default" / "default" / "AGENTS.md").is_file()
    assert calls[0]["cmd"] == ["git", "init", "-q"]
    assert calls[0]["cwd"] == str(workspace)


def test_ensure_workspace_skips_git_init_when_repo_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".git").mkdir(parents=True)

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("git init must not run when .git exists")

    monkeypatch.setattr("subprocess.run", boom)
    desktop_config.ensure_workspace(workspace)
    assert workspace.is_dir()


def test_data_dir_honors_env_override() -> None:
    # DATA_DIR is resolved at import time from ABI_DESKTOP_HOME; derived
    # paths must all live underneath it.
    assert desktop_config.DB_PATH.parent == desktop_config.DATA_DIR
    assert desktop_config.GRAPH_DIR.parent == desktop_config.DATA_DIR
    assert desktop_config.DEFAULT_WORKSPACE.parent == desktop_config.DATA_DIR


def test_default_settings_reference_default_workspace() -> None:
    assert desktop_config.DEFAULT_SETTINGS["workspace_root"] == str(
        desktop_config.DEFAULT_WORKSPACE
    )
    assert desktop_config.DEFAULT_SETTINGS["active_org"] == "default"
    assert desktop_config.DEFAULT_SETTINGS["active_model"] == "default"
    assert desktop_config.DEFAULT_SETTINGS["opencode_bin"] == "opencode"


def test_resolve_system_ontology_paths_includes_bundled_files() -> None:
    paths = resolve_system_ontology_paths()
    assert paths
    names = {path.name for path in paths}
    assert "desktop-routing.ttl" in names
    assert "BFO7BucketsProcessOntology.ttl" in names
    assert all(path.is_file() for path in paths)
    assert (BUNDLED_ONTOLOGY_DIR / "desktop-routing.ttl").is_file()


def test_detect_preferred_workspace_finds_abi_repo_with_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    abi = tmp_path / "abi"
    abi.mkdir()
    (abi / ".git").mkdir()
    (abi / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    monkeypatch.setattr(desktop_config.Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    found = desktop_config.detect_preferred_workspace()
    assert found == abi.resolve()


def test_maybe_upgrade_workspace_setting_from_factory_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    abi = tmp_path / "abi"
    abi.mkdir()
    (abi / ".git").mkdir()
    (abi / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    factory = tmp_path / ".abi-desktop" / "workspace"
    factory.mkdir(parents=True)
    monkeypatch.setattr(desktop_config.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(desktop_config, "DEFAULT_WORKSPACE", factory)
    monkeypatch.setitem(desktop_config.DEFAULT_SETTINGS, "workspace_root", str(factory))

    from desktop.core.store import DesktopStore

    store = DesktopStore(tmp_path / "desktop.db")
    store.update_settings({"workspace_root": str(factory)})
    desktop_config.maybe_upgrade_workspace_setting(store)
    assert store.get_settings()["workspace_root"] == str(abi.resolve())


class TestResolveEnvFiles:
    def test_lists_standard_files_with_key_names_only(self, tmp_path: Path) -> None:
        (tmp_path / ".env.remote").write_text("ANTHROPIC_API_KEY=secret\nFOO=\n")
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test\n")

        files = resolve_env_files(tmp_path)
        assert [entry["name"] for entry in files] == [".env.remote", ".env"]
        assert files[0]["exists"] is True
        assert files[0]["keys"] == ["ANTHROPIC_API_KEY"]
        assert files[1]["keys"] == ["OPENAI_API_KEY"]
        assert "secret" not in str(files)
        assert "sk-test" not in str(files)

    def test_missing_files_reported(self, tmp_path: Path) -> None:
        files = resolve_env_files(tmp_path)
        assert all(entry["exists"] is False for entry in files)
        assert all(entry["keys"] == [] for entry in files)

    def test_merged_env_keys_remote_then_local(self, tmp_path: Path) -> None:
        (tmp_path / ".env.remote").write_text("OPENAI_API_KEY=remote\nSHARED=1\n")
        (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=local\nSHARED=2\n")
        merged = merged_env_keys(tmp_path)
        assert merged["OPENAI_API_KEY"] is True
        assert merged["ANTHROPIC_API_KEY"] is True
        assert merged["SHARED"] is True

    def test_build_shell_env_source_uses_absolute_paths(self, tmp_path: Path) -> None:
        snippet = build_shell_env_source(tmp_path)
        assert "set -a" in snippet
        assert ".env.remote" in snippet
        assert ".env" in snippet
        assert str(tmp_path.resolve()) in snippet

    def test_workspace_env_report_summarizes_provider_keys(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test\n")
        report = workspace_env_report(tmp_path)
        assert report["has_provider_keys"] is True
        assert "OPENAI_API_KEY" in report["provider_keys"]
        assert any(
            key in report["missing_provider_keys"] for key in COMMON_API_KEYS[1:]
        )


def test_parse_and_serialize_recent_workspaces_roundtrip(tmp_path: Path) -> None:
    paths = [str(tmp_path / "a"), str(tmp_path / "b")]
    raw = serialize_recent_workspaces(paths)
    assert parse_recent_workspaces(raw) == [
        str((tmp_path / "a").resolve()),
        str((tmp_path / "b").resolve()),
    ]


def test_add_recent_workspace_dedupes_and_caps(tmp_path: Path) -> None:
    base = [str((tmp_path / f"w{i}").resolve()) for i in range(12)]
    for directory in base:
        Path(directory).mkdir(parents=True, exist_ok=True)
    recent = add_recent_workspace(base, base[3])
    assert recent[0] == base[3]
    assert base[3] not in recent[1:]
    assert len(recent) == 10


def test_workspace_display_name_uses_basename(tmp_path: Path) -> None:
    project = tmp_path / "abi"
    project.mkdir()
    assert workspace_display_name(project) == "abi"
