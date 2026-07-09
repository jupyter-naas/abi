"""Unit tests for org/model workspace layout."""

from __future__ import annotations

from pathlib import Path

import pyoxigraph
import pytest
from pyoxigraph import RdfFormat

from desktop.workspace_layout import (
    DEFAULT_MODEL,
    DEFAULT_ORG,
    OLLAMA_MODELS_BEGIN,
    OLLAMA_MODELS_END,
    ORG_MODEL_FILES,
    build_agent_prompt_prefix,
    list_models,
    list_orgs,
    org_model_path,
    repair_invalid_context_ttl,
    sanitize_segment,
    scaffold_org_model,
    sync_ollama_models_in_instances,
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
    assert "SectionRoute" in ontology
    assert "BFO7Buckets" in ontology
    instances = (created / "instances.ttl").read_text(encoding="utf-8")
    assert "@prefix" in instances
    assert "chatRoute" in instances
    assert 'abid:forSection "chat"' in instances
    assert 'abid:harnessAgent "plan"' in instances
    assert "abi:LanguageModel" in instances
    assert "modelQwenLocal" in instances
    assert 'abid:usesHarness "opencode"' in instances
    assert "abid:modelUri" in instances
    assert "BFO_0000023" in instances
    assert "BFO_0000015" in instances


def test_scaffold_ttl_files_parse_as_turtle(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    created = scaffold_org_model(workspace, "acme", "gpt-5")
    store = pyoxigraph.Store()
    for name in ("ontology.ttl", "instances.ttl"):
        store.load(
            path=str(created / name),
            format=RdfFormat.TURTLE,
        )
    assert len(store) > 0


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


def test_repair_invalid_context_ttl_replaces_unparseable_instances(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    created = scaffold_org_model(workspace, "acme", "coder")
    instances = created / "instances.ttl"
    instances.write_text("@prefix ex: <http://example.org/> .\nex:broken .\n", encoding="utf-8")

    repaired = repair_invalid_context_ttl(workspace, "acme", "coder")
    assert repaired == ["instances.ttl"]
    assert (created / "instances.ttl.bak").is_file()
    store = pyoxigraph.Store()
    store.load(path=str(instances), format=RdfFormat.TURTLE)
    assert len(store) > 0
    assert "chatRoute" in instances.read_text(encoding="utf-8")


def test_sync_ollama_models_in_instances_appends_marked_block(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    created = scaffold_org_model(workspace, "acme", "coder")
    instances = created / "instances.ttl"

    changed = sync_ollama_models_in_instances(
        instances,
        [
            {"name": "qwen2.5-coder:7b", "supports_tools": True},
            {"name": "phi3:mini", "supports_tools": False},
        ],
    )
    assert changed is True
    updated = instances.read_text(encoding="utf-8")
    assert "modelQwenLocal" in updated
    assert OLLAMA_MODELS_BEGIN in updated
    assert OLLAMA_MODELS_END in updated
    assert 'abi:modelRef "ollama/qwen2.5-coder:7b"' in updated
    assert "phi3" not in updated

    changed_again = sync_ollama_models_in_instances(
        instances,
        [{"name": "gemma4:latest", "supports_tools": True}],
    )
    assert changed_again is True
    final = instances.read_text(encoding="utf-8")
    assert final.count(OLLAMA_MODELS_BEGIN) == 1
    assert 'abi:modelRef "ollama/gemma4:latest"' in final
    ollama_block = final.split(OLLAMA_MODELS_BEGIN, 1)[1].split(OLLAMA_MODELS_END, 1)[0]
    assert "qwen2.5-coder" not in ollama_block
    assert "gemma4:latest" in ollama_block

    store = pyoxigraph.Store()
    store.load(path=str(instances), format=RdfFormat.TURTLE)
    assert len(store) > 0
