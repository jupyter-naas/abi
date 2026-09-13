"""TDD: abi documents verbs call the same mutators as HTTP / commands."""

from __future__ import annotations

from click.testing import CliRunner

from naas_abi_cli.cli import _main
from naas_abi_cli.cli.documents import DOCUMENTS_VERBS, documents

_INTRO = '<div class="doc-body"><p class="intro" data-slot="intro">Cover intro stays.</p></div>'


def test_abi_help_lists_documents() -> None:
    result = CliRunner().invoke(_main, ["--help"])
    assert result.exit_code == 0
    assert "documents" in result.output


def test_documents_help_lists_every_verb() -> None:
    result = CliRunner().invoke(documents, ["--help"])
    assert result.exit_code == 0
    for verb in DOCUMENTS_VERBS:
        assert verb in result.output


def test_cli_style_uses_shared_mutator(tmp_path) -> None:
    path = tmp_path / "document.html"
    path.write_text(_INTRO, encoding="utf-8")
    result = CliRunner().invoke(
        documents,
        ["style", "--html", str(path), "--slot", "intro", "--style", "normal"],
    )
    assert result.exit_code == 0, result.output
    text = path.read_text(encoding="utf-8")
    assert "fmz-normal" in text
    assert "Cover intro stays." in text


def test_cli_apply_uses_shared_mutator(tmp_path) -> None:
    path = tmp_path / "document.html"
    path.write_text(
        '<div class="doc-body"><h2>Head</h2><p>Keep</p></div>',
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        documents,
        [
            "apply",
            "--html",
            str(path),
            "--requests",
            '[{"type":"insert_paragraph","text":"Added","after_heading":0}]',
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Added" in path.read_text(encoding="utf-8")
