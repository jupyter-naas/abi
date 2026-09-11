"""Tests for `abi slides` help surface and dry-run wiring."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from naas_abi_cli.cli import _main
from naas_abi_cli.cli.slides import SLIDES_COMMANDS


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_slides_help_lists_exactly_28_commands(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["slides", "--help"])
    assert result.exit_code == 0, result.output
    assert len(SLIDES_COMMANDS) == 28
    for name in SLIDES_COMMANDS:
        assert name in result.output, name


def test_abi_help_lists_slides(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["--help"])
    assert result.exit_code == 0, result.output
    assert "slides" in result.output


def test_slides_list_requires_workspace(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["slides", "list", "--dry-run"])
    assert result.exit_code != 0
    assert "NEXUS_WORKSPACE_ID" in result.output


def test_slides_list_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        ["slides", "list", "--workspace", "ws-1", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/slides/projects?workspace_id=ws-1"


def test_slides_create_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "slides",
            "create",
            "--workspace",
            "ws-1",
            "--title",
            "Q3 review",
            "--slug",
            "q3-review",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/slides/projects"
    assert payload["body"]["title"] == "Q3 review"
    assert payload["body"]["slug"] == "q3-review"
    assert payload["body"]["template_id"] == "abi/minimal-light-v1"


def test_slides_insert_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "slides",
            "insert",
            "q3-review",
            "--workspace",
            "ws-1",
            "--after",
            "0",
            "--layout",
            "cover",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/slides/projects/q3-review/slides/insert"
    assert payload["body"]["after_index"] == 0
    assert payload["body"]["layout"] == "cover"


def test_slides_export_pptx_dry_run_names_the_gap(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "slides",
            "export",
            "q3-review",
            "--format",
            "pptx",
            "-o",
            "out.pptx",
            "--workspace",
            "ws-1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "browser-only" in payload["error"]


def test_slides_chat_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "slides",
            "chat",
            "q3-review",
            "-m",
            "Rewrite the cover",
            "--workspace",
            "ws-1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["agent"] == "SlidesAgent"
    assert payload["slug"] == "q3-review"
