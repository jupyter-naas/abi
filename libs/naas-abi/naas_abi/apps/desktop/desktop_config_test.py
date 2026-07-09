"""Unit tests for desktop_config filesystem helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop import desktop_config
from desktop.desktop_config import (
    COMMON_API_KEYS,
    build_shell_env_source,
    merged_env_keys,
    resolve_env_files,
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
    assert desktop_config.DEFAULT_SETTINGS["opencode_bin"] == "opencode"


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

    def test_workspace_env_report_summarizes_provider_keys(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test\n")
        report = workspace_env_report(tmp_path)
        assert report["has_provider_keys"] is True
        assert "OPENAI_API_KEY" in report["provider_keys"]
        assert any(key in report["missing_provider_keys"] for key in COMMON_API_KEYS[1:])
