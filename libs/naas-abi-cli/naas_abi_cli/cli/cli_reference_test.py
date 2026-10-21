"""The CLI reference page documents the whole command tree.

Walks the Click tree of `abi` and fails when `https://docs.naas.ai/user-guide/reference/cli`
misses a command or one of its options, or shows a command, an option or a heading
that does not exist. The same check runs on the `abi ...` examples of every
hand-written page of the site.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
import pytest

from naas_abi_cli.cli import _main

NEXUS_API_OPTIONS = {
    "--api-url",
    "--token",
    "--auth-email",
    "--auth-password",
    "--dry-run",
}
NEXUS_GROUPS = ("abi org", "abi user", "abi workspace")
SHARED_OPTIONS_HEADING = "Nexus API options"

HEADING = re.compile(r"^(#{2,6})\s+`?(abi(?: [a-z][a-z0-9-]*)*)`?\s*$")
ANY_HEADING = re.compile(r"^#{1,6}\s")
FENCE = re.compile(r"^\s*```(\w*)")
SHELL_FENCES = {"", "bash", "sh", "shell", "console", "zsh"}


def _docs_dir() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        docs = parent / "docs" / "site" / "docs"
        if docs.is_dir():
            return docs
    return None


DOCS = _docs_dir()
pytestmark = pytest.mark.skipif(
    DOCS is None, reason="the docs site is not in this checkout"
)
CLI_PAGE = (DOCS or Path()) / "user-guide" / "reference" / "cli.md"

# Pages whose `abi ...` lines are not checked: dated release notes (they show
# the commands of their day) and the generated library reference.
EXAMPLE_SKIP_PARTS = ("release-notes", "reference/libraries")


def _commands() -> dict[str, click.Command]:
    """Every visible command and group, by path: `abi new project`."""
    found: dict[str, click.Command] = {}

    def walk(command: click.Command, path: str) -> None:
        for name, child in sorted(getattr(command, "commands", {}).items()):
            if child.hidden:
                continue
            found[f"{path} {name}"] = child
            walk(child, f"{path} {name}")

    walk(_main, "abi")
    return found


def _long_options(command: click.Command) -> set[str]:
    options: set[str] = set()
    for param in command.params:
        if isinstance(param, click.Option):
            options.update(
                o for o in (*param.opts, *param.secondary_opts) if o.startswith("--")
            )
    options.discard("--help")
    return options


def _sections(text: str) -> dict[str, str]:
    """The text under each `abi ...` heading, up to the next heading of any kind."""
    sections: dict[str, str] = {}
    current: str | None = None
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and ANY_HEADING.match(line):
            match = HEADING.match(line)
            current = match.group(2) if match else None
            if current is not None:
                sections.setdefault(current, "")
            continue
        if current is not None:
            sections[current] += line + "\n"
    return sections


def _section_named(text: str, title: str) -> str:
    """The text under the heading `title`, up to the next heading of the same or a higher level."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(#+)\s+{re.escape(title)}\s*$", line)
        if match:
            level = len(match.group(1))
            body: list[str] = []
            for follow in lines[index + 1 :]:
                heading = re.match(r"^(#+)\s", follow)
                if heading and len(heading.group(1)) <= level:
                    break
                body.append(follow)
            return "\n".join(body)
    return ""


def _resolve(tokens: list[str]) -> tuple[str, click.Command, list[str]] | None:
    """The command an `abi ...` line runs, and the tokens after it."""
    command: click.Command = _main
    path = "abi"
    rest = tokens
    while isinstance(command, click.Group) and rest and rest[0] in command.commands:
        command = command.commands[rest[0]]
        path += f" {rest[0]}"
        rest = rest[1:]
    if isinstance(command, click.Group) and rest and not rest[0].startswith("-"):
        return None
    return path, command, rest


def _example_lines(text: str) -> list[str]:
    """The `abi ...` commands of the fenced blocks, one per logical line."""
    lines: list[str] = []
    in_fence = False
    shell = False
    pending = ""
    for raw in text.splitlines():
        opening = FENCE.match(raw)
        if opening:
            in_fence = not in_fence
            shell = in_fence and opening.group(1).lower() in SHELL_FENCES
            pending = ""
            continue
        if not (in_fence and shell):
            continue
        line = pending + raw.strip()
        pending = ""
        if line.endswith("\\"):
            pending = line[:-1].rstrip() + " "
            continue
        line = re.sub(r"\s+#.*$", "", line).removeprefix("$ ").strip()
        # `(cd src/x && abi new agent ...)`, `a && abi ...`, `x | abi ...`.
        for part in re.split(r"&&|\|\||;|\(|\)|\|", line):
            part = part.strip()
            if part.startswith("abi ") or part == "abi":
                lines.append(part)
    return lines


def _check_example(line: str) -> str | None:
    try:
        tokens = shlex.split(line)[1:]
    except ValueError:
        return None  # a placeholder with an unbalanced quote
    resolved = _resolve(tokens)
    if resolved is None:
        return f"`{line}`: no such command"
    path, command, rest = resolved
    if command.context_settings.get("ignore_unknown_options"):
        return None  # `abi run script` forwards the options after its path
    known = _long_options(command) | {"--help"}
    for token in rest:
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            if name not in known:
                return f"`{line}`: `{path}` has no option {name}"
    return None


def test_the_reference_page_exists() -> None:
    assert CLI_PAGE.is_file(), f"{CLI_PAGE} is missing"


def test_every_command_has_a_section_on_the_reference_page() -> None:
    sections = _sections(CLI_PAGE.read_text())
    missing = [path for path in _commands() if path not in sections]
    assert not missing, (
        "commands missing from https://docs.naas.ai/user-guide/reference/cli "
        f"(add a heading like `## `{missing[0]}``): {missing}"
    )


def test_every_option_is_documented_in_its_command_section() -> None:
    text = CLI_PAGE.read_text()
    sections = _sections(text)
    shared = _section_named(text, SHARED_OPTIONS_HEADING)
    gaps: list[str] = []
    for path, command in _commands().items():
        if isinstance(command, click.Group) or path not in sections:
            continue
        for option in sorted(_long_options(command)):
            if option in NEXUS_API_OPTIONS and path.startswith(NEXUS_GROUPS):
                if option not in shared:
                    gaps.append(f"{option} (shared) of {path}")
                continue
            if option not in sections[path]:
                gaps.append(f"{option} of {path}")
    assert not gaps, f"options missing from the reference page: {gaps}"


def test_the_reference_page_documents_no_command_that_does_not_exist() -> None:
    sections = _sections(CLI_PAGE.read_text())
    unknown = sorted(set(sections) - set(_commands()) - {"abi"})
    assert not unknown, f"cli.md has headings for commands that do not exist: {unknown}"


def _hand_written_pages() -> list[Path]:
    assert DOCS is not None
    pages: list[Path] = []
    for pattern in ("*.md", "*.mdx"):
        for page in DOCS.rglob(pattern):
            relative = page.relative_to(DOCS).as_posix()
            if any(part in relative for part in EXAMPLE_SKIP_PARTS):
                continue
            pages.append(page)
    return sorted(pages)


@pytest.mark.parametrize(
    "page",
    _hand_written_pages() if DOCS else [],
    ids=lambda page: page.relative_to(DOCS).as_posix() if DOCS else str(page),
)
def test_the_abi_examples_of_a_page_exist(page: Path) -> None:
    problems = [
        problem
        for line in _example_lines(page.read_text())
        if (problem := _check_example(line))
    ]
    assert not problems, f"{page.name}: " + "; ".join(problems)
