"""Unit tests for org/model workspace layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop.workspace_layout import (
    DEFAULT_MODEL,
    DEFAULT_ORG,
    ORG_MODEL_FILES,
    build_agent_prompt_prefix,
    list_models,
    list_orgs,
    org_model_path,
    sanitize_segment,
    scaffold_org_model,
)


def test_sanitize_segment_rejects_empty_and_traversal() -> None:
    assert sanitize_segment("acme") == "acme"
    assert sanitize_segment("  my-org  ") == "my-org"
    with pytest.raises(ValueError, match="invalid"):
        sanitize_segment("")
    with pytest.raises(ValueError, match="invalid"):
        sanitize_segment("..")
    with pytest.raises(ValueError, match="invalid"):
        sanitize_segment("org/model")


def test_org_model_path_resolves_under_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    path = org_model_path(workspace, "Acme", "gpt-5")
    assert path == (workspace / "Acme" / "gpt-5").resolve()


def test_scaffold_org_model_creates_templates(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    created = scaffold_org_model(workspace, "default", "default")

    assert created.is_dir()
    for name in ORG_MODEL_FILES:
        file_path = created / name
        assert file_path.is_file(), name
        assert file_path.read_text(encoding="utf-8")

    agents = (created / "AGENTS.md").read_text(encoding="utf-8")
    assert "default/default" in agents
    memory = (created / "MEMORY.md").read_text(encoding="utf-8")
    assert "default/default" in memory
    ontology = (created / "ontology.ttl").read_text(encoding="utf-8")
    assert "@prefix" in ontology
    instances = (created / "instances.ttl").read_text(encoding="utf-8")
    assert "@prefix" in instances


def test_scaffold_org_model_is_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    first = scaffold_org_model(workspace, "org-a", "model-b")
    (first / "AGENTS.md").write_text("# Custom agents\n", encoding="utf-8")
    second = scaffold_org_model(workspace, "org-a", "model-b")
    assert second == first
    assert (first / "AGENTS.md").read_text(encoding="utf-8") == "# Custom agents\n"


def test_list_orgs_and_models(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    (workspace / "node_modules").mkdir()
    scaffold_org_model(workspace, "alpha", "fast")
    scaffold_org_model(workspace, "alpha", "slow")
    scaffold_org_model(workspace, "beta", "main")

    assert list_orgs(workspace) == ["alpha", "beta"]
    assert list_models(workspace, "alpha") == ["fast", "slow"]
    assert list_models(workspace, "beta") == ["main"]
    assert list_models(workspace, "missing") == []


def test_list_orgs_ignores_non_model_dirs(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "random-dir").mkdir()
    assert list_orgs(workspace) == []


def test_build_agent_prompt_prefix_includes_markdown(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    path = scaffold_org_model(workspace, "acme", "coder")
    (path / "AGENTS.md").write_text("# Agent rules\nBe concise.\n", encoding="utf-8")
    (path / "MEMORY.md").write_text("# Memory\nRemember X.\n", encoding="utf-8")

    prefix = build_agent_prompt_prefix(workspace, "acme", "coder")
    assert "Agent rules" in prefix
    assert "Remember X" in prefix
    assert prefix.endswith("\n\n")


def test_build_agent_prompt_prefix_empty_when_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert build_agent_prompt_prefix(workspace, "nope", "nope") == ""


def test_default_org_and_model_constants() -> None:
    assert DEFAULT_ORG == "default"
    assert DEFAULT_MODEL == "default"
