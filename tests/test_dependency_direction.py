"""ABI must not import zen, or name it in a string.

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

A second scan covers the same coupling spelled as a string. The slides
template resolver knew about two template trees, ABI's own and zen's, through
a "zen/<id>" prefix, an asset path of "src/zen/assets/slides/templates", a
ZEN_SLIDES_TEMPLATES_DIR env var, a ("abi", "zen") tuple, and an (abi|zen)
alternative in a regex. Not one import among them, so TID251 and the scan
above both read the tree as clean while ABI shipped a hardcoded list of its
consumers. Template trees are configuration now, and this keeps them that way.

The string scan fires only on the qualified spellings: a separator on both
sides of the name, as in a path, a dotted module, or an identifier, plus a
regex alternative. A bare "zen" is not an offence, because it is what prose
and a label look like and because the argument that makes an import fail in a
test defending this invariant is spelled exactly that way. The one exception
is a bare mention enumerated beside another literal, ("abi", "zen"), which is
a hardcoded source list and nothing else. Docstrings are skipped, comments
never reach the AST, and the cost of that pair is one rule for a future
author: explain this in a docstring or a comment, not in a string constant.

Both rules are deliberately narrow: one named package, no allowlist. The
general form, "naas-abi must not import anything outside its own
distribution", is worth more but cannot be made reliable here. It needs the full set of legitimate
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
import re
from collections.abc import Callable
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

_QUALIFIED_RE = re.compile(
    # A path segment, a dotted module, or an identifier segment: a separator on
    # both sides. That is what a template id, an asset path and an env var name
    # look like, and requiring the separator is what keeps `frozen`, `zenith`,
    # `citizen` and `zendesk` out without an allowlist.
    rf"(?:^|[^0-9A-Za-z]){BANNED_ROOT}[/.\\_-]"
    # Or an alternative in a regex, which is how the two accepted namespaces
    # were spelled: (?P<source>abi|zen)/. The delimiter here is Python syntax
    # when it is a call, so a literal that ends in `zen` does not match.
    rf"|[|(]{BANNED_ROOT}(?![0-9A-Za-z])",
    re.IGNORECASE,
)

STRING_RULE = (
    f"ABI must not hardcode {BANNED_ROOT}. A consumer's name in a template "
    f"id, an asset path, an env var, or a test fixture couples ABI to one "
    f"downstream application just as an import does, and no import linter can "
    f"see it. Take the value from configuration and let the consumer name "
    f"itself. Offending literals:"
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


def _string_literals(tree: ast.AST) -> list[ast.Constant]:
    """Every string literal except the ones that are a statement on their own.

    A bare string expression is a docstring, module, class, function, or the
    attribute kind. That is where this rule and the history behind it get
    explained, so scanning them would make the explanation the offence.
    Comments never reach the AST, so they are out for free.
    """
    documentation = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in documentation
    ]


def _enumerated_strings(tree: ast.AST) -> set[int]:
    """Literals sitting beside another literal in one collection.

    This is the shape of a hardcoded source list: ("abi", "zen"). A bare
    mention anywhere else is prose, a label, or the argument that makes an
    import fail in a test defending this invariant, and none of those is an
    offence. Requiring a neighbour is what separates them without an
    allowlist.
    """
    enumerated: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            elements = node.elts
        elif isinstance(node, ast.Dict):
            elements = [key for key in node.keys if key is not None]
        else:
            continue
        literals = [
            e for e in elements if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        if len(literals) > 1:
            enumerated.update(id(e) for e in literals)
    return enumerated


def _string_offences(source: str, label: str) -> list[str]:
    """Every hardcoded spelling of the banned name in one module.

    Parsed rather than grepped, for the same reason as the import scan: the
    text of this file, the rule's own message, and the docstring on the code
    that was moved out of the downstream repo all name it legitimately.
    """
    tree = ast.parse(source)
    enumerated = _enumerated_strings(tree)
    found: list[str] = []
    for node in _string_literals(tree):
        qualified = _QUALIFIED_RE.search(node.value)
        bare = node.value.strip().lower() == BANNED_ROOT and id(node) in enumerated
        if qualified or bare:
            found.append(f"{label}:{node.lineno}: {node.value!r}")
    return found


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


def _scan_libs(collect: Callable[[str, str], list[str]]) -> list[str]:
    offences: list[str] = []
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        if _SKIP_DIRS.intersection(path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            offences += collect(source, str(path.relative_to(SCAN_ROOT.parent)))
        except SyntaxError:
            # CLI scaffolding templates are not valid Python until rendered.
            continue
    return offences


def test_libs_do_not_import_zen() -> None:
    assert not (offences := _scan_libs(_offences)), "\n".join([RULE, *offences])


def test_libs_do_not_hardcode_zen_in_a_string() -> None:
    assert not (offences := _scan_libs(_string_offences)), "\n".join(
        [STRING_RULE, *offences]
    )


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


def test_the_string_scan_reports_the_file_and_the_line() -> None:
    source = 'IDS = ["abi/minimal-light-v1", "zen/tenant-only-v1"]\n'

    (offence,) = _string_offences(source, "libs/naas-abi/naas_abi/slides.py")

    assert offence.startswith("libs/naas-abi/naas_abi/slides.py:1:")
    assert "zen/tenant-only-v1" in offence


@pytest.mark.parametrize(
    "source",
    [
        # Every form the slides template resolver actually used.
        'IDS = ("zen/tenant-only-v1",)',
        '_ORIGIN = "src/zen/assets/slides/templates"',
        '_ENV = "ZEN_SLIDES_TEMPLATES_DIR"',
        'RE = r"^(?:(?P<source>abi|zen)/)?(?P<stem>[a-z0-9-]+)$"',
        'SOURCES = ("abi", "zen")',
        'SOURCES = ["abi", "zen"]',
        'SOURCES = {"abi", "zen"}',
        'ORIGINS = {"abi": "packaged", "zen": "src/zen"}',
        'def f(stem):\n    return f"zen/{stem}"\n',
        'PATH = "/app/zen-assets/slides"',
        'MOD = "zen.tools.WebTools"',
    ],
)
def test_the_string_scan_catches_every_hardcoded_form(source: str) -> None:
    """The forms below are the ones that were in the tree, not invented ones."""
    assert _string_offences(source, "sample.py"), f"scan missed: {source}"


@pytest.mark.parametrize(
    "source",
    [
        # A separator on both sides is what keeps these out.
        'PATH = "/var/frozen/cache"',
        'NAME = "zenith-v1"',
        'FIELD = "citizen_id"',
        'COUNT = "a dozen_things"',
        'HOST = "zendesk.example.com"',
        # A bare mention on its own. Prose, a label, or the argument that
        # makes an import fail in a test defending this very invariant.
        'LABEL = "zen"',
        '_unimportable("zen")',
        'raise AssertionError("must not import zen")',
        # Docstrings and comments, which is where the rule gets explained.
        '"""Ported from the zen WebTools wrapper. Do not import zen.tools."""',
        "# _ORIGIN = 'src/zen/assets/slides/templates'",
        'def f():\n    """Kept out of zen/ on purpose."""\n    return 1\n',
    ],
)
def test_the_string_scan_ignores_look_alikes(source: str) -> None:
    """A rule that cries wolf gets deleted by the first person it annoys."""
    assert _string_offences(source, "sample.py") == [], f"false positive: {source}"
