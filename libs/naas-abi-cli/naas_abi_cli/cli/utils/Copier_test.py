"""Tests for Copier's rendering and post-render formatting.

Generated Python has to survive the repo's own lint gate, so the Copier keeps
the trailing newline Jinja would otherwise strip and runs `ruff format` over
the files it wrote. Both are easy to regress silently, hence these tests.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from naas_abi_cli.cli.utils.Copier import Copier

RUFF = shutil.which("ruff")
needs_ruff = pytest.mark.skipif(RUFF is None, reason="ruff not on PATH")


def _render(tmp_path: Path, template: str, values: dict, filename: str) -> Path:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / filename).write_text(template, encoding="utf-8")

    destination = tmp_path / "out"
    destination.mkdir()

    Copier(str(templates), str(destination)).copy(values=values)
    return destination / filename.replace("{{name}}", values.get("name", ""))


def test_generated_python_keeps_its_trailing_newline(tmp_path: Path) -> None:
    """Jinja strips one trailing newline by default; ruff format rejects that."""
    out = _render(tmp_path, "x = '{{name}}'\n", {"name": "Thing"}, "mod.py")

    assert out.read_text(encoding="utf-8").endswith("\n")


def test_non_python_files_also_keep_their_trailing_newline(tmp_path: Path) -> None:
    out = _render(tmp_path, "key: {{name}}\n", {"name": "value"}, "conf.yaml")

    assert out.read_text(encoding="utf-8") == "key: value\n"


@needs_ruff
@pytest.mark.parametrize(
    "name",
    [
        "A",
        "Medium",
        "SuperExtremelyLongAndVerboseEnterpriseReportingAssistant",
    ],
)
def test_generated_python_is_ruff_format_clean_at_any_name_length(
    tmp_path: Path, name: str
) -> None:
    """Rendering shifts wrapping, so only formatting *after* render is reliable.

    This template renders to a call that fits on one line for a short name and
    must wrap for a long one -- exactly the case a pre-formatted template gets
    wrong.
    """
    assert RUFF is not None  # guaranteed by the skipif above
    template = (
        "def run(self, parameters: {{name}}Parameters, other: {{name}}Config) -> dict:\n"
        "    return do_something({{name}}Parameters(**kwargs), {{name}}Config(**kwargs))\n"
    )
    out = _render(tmp_path, template, {"name": name}, "mod.py")

    result = subprocess.run(
        [RUFF, "format", "--check", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@needs_ruff
def test_formatting_only_touches_generated_files(tmp_path: Path) -> None:
    """The destination may be the user's project -- never reformat their code."""
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "generated.py").write_text("x = {{name}}\n", encoding="utf-8")

    destination = tmp_path / "out"
    destination.mkdir()
    untouched = destination / "pre_existing.py"
    # Deliberately unformatted: ruff would rewrite this if it were included.
    original = "y   =    1\n\n\n\nz=2\n"
    untouched.write_text(original, encoding="utf-8")

    Copier(str(templates), str(destination)).copy(values={"name": "1"})

    assert untouched.read_text(encoding="utf-8") == original


def test_generation_succeeds_when_ruff_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruff is not a runtime dependency -- its absence must not break scaffolding."""
    monkeypatch.setattr("naas_abi_cli.cli.utils.Copier.shutil.which", lambda _: None)

    def _boom(*args, **kwargs):
        raise FileNotFoundError("no ruff here")

    monkeypatch.setattr("naas_abi_cli.cli.utils.Copier.subprocess.run", _boom)

    out = _render(tmp_path, "x = '{{name}}'\n", {"name": "Thing"}, "mod.py")

    assert out.read_text(encoding="utf-8") == "x = 'Thing'\n"
