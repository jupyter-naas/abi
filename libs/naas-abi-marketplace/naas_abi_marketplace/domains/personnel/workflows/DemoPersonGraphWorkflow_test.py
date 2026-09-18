"""Tests for demo person graph workflow."""

from __future__ import annotations

from pathlib import Path

from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE, DEMO_SOURCE_DIR
from naas_abi_marketplace.domains.personnel.workflows.DemoPersonGraphWorkflow import (
    DemoPersonGraphWorkflow,
    DemoPersonGraphWorkflowConfiguration,
    DemoPersonGraphWorkflowParameters,
)


def test_demo_mode_writes_local_ttl(tmp_path: Path) -> None:
    output = tmp_path / "personnel.ttl"
    workflow = DemoPersonGraphWorkflow(DemoPersonGraphWorkflowConfiguration())
    result = workflow.run(
        DemoPersonGraphWorkflowParameters(
            mode="demo",
            source_dir=str(DEMO_SOURCE_DIR),
            output_path=str(output),
        )
    )
    assert result["mode"] == "demo"
    assert output.is_file()
    assert result["instance_triples"] > 0
    assert result["person_count"] == len(list(DEMO_SOURCE_DIR.glob("*/index.json")))


def test_demo_mode_default_output_path_exists_after_run(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "graphs" / "demo" / "personnel.ttl"
    monkeypatch.setattr(
        "naas_abi_marketplace.domains.personnel.graph.demo.DEMO_GRAPH_FILE",
        target,
    )
    workflow = DemoPersonGraphWorkflow(DemoPersonGraphWorkflowConfiguration())
    workflow.run(
        DemoPersonGraphWorkflowParameters(mode="demo", source_dir=str(DEMO_SOURCE_DIR))
    )
    assert target.is_file()
