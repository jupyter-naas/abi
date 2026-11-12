"""What an image built from the repository root receives: no .env holding
values, and the CLI's .env templates, which the released image renders."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _pattern(pattern: str) -> re.Pattern[str]:
    """A .dockerignore pattern (Go filepath.Match plus `**`) as a regex."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    # A directory pattern also excludes what is below it.
    return re.compile(out.rstrip("/") + "(?:/.*)?")


def _excluded(path: str, rules: list[tuple[bool, re.Pattern[str]]]) -> bool:
    excluded = False
    for negated, pattern in rules:  # the last matching rule wins
        if pattern.fullmatch(path):
            excluded = not negated
    return excluded


def _rules() -> list[tuple[bool, re.Pattern[str]]]:
    rules = []
    for line in (REPO / ".dockerignore").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        rules.append((negated, _pattern(line.lstrip("!").lstrip("/"))))
    return rules


def test_image_context_keeps_dotenv_values_out() -> None:
    rules = _rules()
    for path in (".env", ".env.local", "libs/naas-abi/.env", "storage/x", "libs/naas-abi-core/.venv/bin/python"):
        assert _excluded(path, rules), path


def test_image_context_keeps_the_cli_templates_and_examples() -> None:
    rules = _rules()
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    dotenv = [path for path in tracked if re.search(r"(^|/)\.env($|\.)", path)]
    assert "libs/naas-abi-cli/naas_abi_cli/cli/deploy/templates/local/.env" in dotenv
    assert "libs/naas-abi-cli/naas_abi_cli/cli/new/templates/project/.env" in dotenv
    # Every tracked dotenv file is a template or an example: all reach the image.
    assert [path for path in dotenv if _excluded(path, rules)] == []
