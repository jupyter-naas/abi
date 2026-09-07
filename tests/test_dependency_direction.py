"""ABI must not import zen.

zen installs ABI as a package, so the dependency runs one way. An import in the
other direction resolves only in a checkout that happens to have zen on its
path and fails on every other install.

The failure is quiet, which is why this is worth a test. AbiAgent imported
zen.tools.WebTools behind a bare `except Exception` logged at debug level, so on
a bare install the web search tools never bound, and the slides research gate
then rejected every deck write forever because nothing could fill the query
list it waits on. No error surfaced anywhere.

Ruff enforces the same rule at lint time, through the TID251 banned-api entry in
the root pyproject, and that is both cheaper and earlier. This scan is not a
duplicate of it. Ruff cannot cover the whole invariant:

  - Ruff resolves its settings from the nearest pyproject.toml carrying a
    [tool.ruff] table, and that table overrides rather than extends the one
    above it. libs/naas-abi/naas_abi/apps/nexus/apps/api has its own, so the
    entire Nexus API subtree sits outside the reach of the root banned-api
    entry, and any nested config added later opens the same hole in silence.
  - importlib.import_module("zen.x") is a string at lint time. No import linter
    can see it, and dynamic import is the idiom reached for exactly the optional
    and lazy imports that produced this bug.

This scan walks one directory tree it owns, so its coverage does not depend on
where config files happen to sit.

The rule is deliberately narrow: one named package, no allowlist. The general
form, "naas-abi must not import anything outside its own distribution", is
worth more but cannot be made reliable here. It needs the full set of legitimate
import names, which means resolving every import to a distribution through
importlib.metadata, which reads the environment. Its verdict would then change
with which extras you synced, and it would call a lazy dagster import an
offence on a venv without the dagster extra. A rule that cries wolf gets
deleted by the first person it annoys. zen is a specific, named, downstream
application that will never be an ABI distribution, so banning it needs no
allowlist and cannot drift.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BANNED_ROOT = "zen"
SCAN_ROOT = Path(__file__).resolve().parents[1] / "libs"
_SKIP_DIRS = {
    ".git",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
}

RULE = (
    f"ABI must not import {BANNED_ROOT}. zen depends on ABI, so an import in "
    f"this direction resolves only in a zen checkout and fails on every other "
    f"install, quietly if it sits behind a broad except. Move the code into "
    f"naas_abi and import it from there. Offending imports:"
)


def _is_banned(module: str | None) -> bool:
    """True for the banned root and its submodules, not for names containing it.

    Splitting on the separator is what keeps `zenith` and `frozen` out.
    """
    return bool(module) and module.split(".")[0] == BANNED_ROOT


def _dynamic_target(node: ast.Call) -> str | None:
    """The module name a dynamic import call asks for, when it is a literal.

    A call whose argument is a variable is invisible here, the same way it is
    invisible to a linter. Nothing can resolve it without running the code.
    """
    func = node.func
    called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if called not in ("import_module", "__import__"):
        return None
    args = list(node.args) + [kw.value for kw in node.keywords if kw.arg == "name"]
    for arg in args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _offences(source: str, label: str) -> list[str]:
    """Every banned import in one module, as `path:line: form`.

    Parsing rather than matching text. A regex over source would have to be
    told about comments, docstrings, and strings that quote the rule itself,
    and the version of it that only catches `from zen.x import y` reads as a
    working guard while missing two of the three forms.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_banned(alias.name):
                    found.append(f"{label}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            # level > 0 is a relative import, which cannot reach another
            # distribution however its module is spelled.
            if node.level == 0 and _is_banned(node.module):
                names = ", ".join(alias.name for alias in node.names)
                form = f"from {node.module} import {names}"
                found.append(f"{label}:{node.lineno}: {form}")
        elif isinstance(node, ast.Call):
            target = _dynamic_target(node)
            if _is_banned(target):
                found.append(f"{label}:{node.lineno}: dynamic import of {target}")
    return found


def test_libs_do_not_import_zen() -> None:
    offences: list[str] = []
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        if _SKIP_DIRS.intersection(path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            offences += _offences(source, str(path.relative_to(SCAN_ROOT.parent)))
        except SyntaxError:
            # CLI scaffolding templates are not valid Python until rendered.
            continue

    assert not offences, "\n".join([RULE, *offences])


def test_the_scan_reports_the_file_and_the_line() -> None:
    """A guard that only says "you broke a rule" costs more than it saves."""
    source = "import os\n\nfrom zen.tools.WebTools import make_web_search_tool\n"

    (offence,) = _offences(source, "libs/naas-abi/naas_abi/agents/AbiAgent.py")

    assert offence.startswith("libs/naas-abi/naas_abi/agents/AbiAgent.py:3:")
    assert "zen.tools.WebTools" in offence
    assert "make_web_search_tool" in offence


@pytest.mark.parametrize(
    "source",
    [
        "from zen.tools.WebTools import make_web_search_tool",
        "from zen import tools",
        "import zen.tools.WebTools",
        "import zen",
        "import zen.tools as t",
        'importlib.import_module("zen.tools.WebTools")',
        'import_module("zen")',
        'importlib.import_module(name="zen.tools")',
        '__import__("zen.tools")',
        "def f():\n    from zen.tools.WebTools import x\n",
        "try:\n    import zen\nexcept ImportError:\n    pass\n",
    ],
)
def test_the_scan_catches_every_banned_form(source: str) -> None:
    """Kept as a permanent test, not a one-off manual check.

    A scan that stops matching is worse than no scan, because it reports a
    clean tree. This is the part that goes red if the detection rots.
    """
    assert _offences(source, "sample.py"), f"scan missed: {source}"


@pytest.mark.parametrize(
    "source",
    [
        "zenith = 1",
        "from frozen import thaw",
        "import zoneinfo",
        "zen_like = {'zen': 1}",
        "# from zen.tools.WebTools import make_web_search_tool",
        '"""from zen.tools import x"""',
        'RULE = "ABI must not import zen.tools from anywhere"',
        "from .zen import local",
        "importlib.import_module(module_name)",
        'load("zen.tools.WebTools")',
    ],
)
def test_the_scan_ignores_look_alikes(source: str) -> None:
    """A rule with false positives is a rule someone deletes.

    The last two matter most: this file and the rule's own message both spell
    the banned name out, and so will the next place the rule is documented.
    """
    assert _offences(source, "sample.py") == [], f"false positive on: {source}"
