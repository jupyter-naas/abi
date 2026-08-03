"""Tests for onto2py's linting of generated output.

The generator lints what it writes so downstream repos can run `ruff check`
over generated files. These cover the two ways that used to fail invisibly:
a ruff that is missing or erroring, and pre-existing class files that were
never re-linted after the linter's rules moved on.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

from naas_abi_core.utils.onto2py.onto2py import (
    ClassInfo,
    _run_ruff,
    create_class_files,
)


def _class_info(name: str) -> ClassInfo:
    return ClassInfo(
        name=name,
        uri=f"http://example.org/onto#{name}",
        parent_classes=[],
        properties=[],
    )


def test_run_ruff_warns_when_ruff_is_missing(capsys):
    """A missing ruff must be reported, not silently skipped."""
    with patch("naas_abi_core.utils.onto2py.onto2py._find_ruff", return_value=None):
        _run_ruff(["some_file.py"])

    out = capsys.readouterr().out
    assert "ruff not found" in out
    assert "unlinted" in out


def test_run_ruff_reports_unresolved_violations(capsys):
    """Non-zero exit means the generator emitted code the linter rejects."""
    completed = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="E501 line too long", stderr=""
    )
    with (
        patch("naas_abi_core.utils.onto2py.onto2py._find_ruff", return_value="ruff"),
        patch(
            "naas_abi_core.utils.onto2py.onto2py.subprocess.run",
            return_value=completed,
        ),
    ):
        _run_ruff(["some_file.py"])

    out = capsys.readouterr().out
    assert "unresolved issues" in out
    assert "exit 1" in out
    assert "E501 line too long" in out


def test_run_ruff_is_silent_on_success(capsys):
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with (
        patch("naas_abi_core.utils.onto2py.onto2py._find_ruff", return_value="ruff"),
        patch(
            "naas_abi_core.utils.onto2py.onto2py.subprocess.run",
            return_value=completed,
        ),
    ):
        _run_ruff(["some_file.py"])

    assert capsys.readouterr().out == ""


def test_run_ruff_skips_empty_path_list(capsys):
    """No paths means nothing to lint - and nothing to warn about."""
    with patch(
        "naas_abi_core.utils.onto2py.onto2py._find_ruff", return_value=None
    ) as find_ruff:
        _run_ruff([])

    assert capsys.readouterr().out == ""
    find_ruff.assert_not_called()


def test_create_class_files_lints_preexisting_files(tmp_path: Path):
    """Existing class files are re-linted, not frozen at the rules that made them.

    Without this, a class file keeps whatever formatting the ruff of the day
    produced and drifts out of step with the repo's linter forever.
    """
    ontologies = tmp_path / "domain" / "ontologies"
    ontologies.mkdir(parents=True)
    ttl_file = ontologies / "modules" / "DomainOntology.ttl"
    ttl_file.parent.mkdir(parents=True)
    ttl_file.write_text("# ttl stub\n")
    py_file = ttl_file.with_suffix(".py")
    py_file.write_text("# generated stub\n")

    classes = {"http://example.org/onto#Alpha": _class_info("Alpha")}

    # First pass creates the class file.
    with patch("naas_abi_core.utils.onto2py.onto2py._run_ruff") as run_ruff:
        create_class_files(str(ttl_file), classes, py_file)
        created = run_ruff.call_args.args[0]

    assert len(created) == 1, "first pass should create and lint one class file"
    assert created[0].endswith("Alpha.py")

    # Second pass skips the now-existing file, but must still lint it.
    with patch("naas_abi_core.utils.onto2py.onto2py._run_ruff") as run_ruff:
        create_class_files(str(ttl_file), classes, py_file)
        linted = run_ruff.call_args.args[0]

    assert linted == created, "pre-existing class files must still be linted"
