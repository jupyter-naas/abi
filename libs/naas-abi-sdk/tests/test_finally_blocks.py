"""No `return`, `break` or `continue` leaves a `finally` block (PEP 765).

Python 3.14 and later warn on these when they compile the module, and the
identity provider's image runs this SDK on a newer interpreter than CI does.
The check reads the source, so it holds on every Python the tests run on.
"""

import ast
from pathlib import Path

import naas_abi_sdk

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)


def _exits(node: ast.AST, in_loop: bool) -> list[ast.stmt]:
    if isinstance(node, _SCOPES):
        return []
    if isinstance(node, ast.Return) or (
        isinstance(node, (ast.Break, ast.Continue)) and not in_loop
    ):
        return [node]
    if isinstance(node, _LOOPS):
        # The loop's `else` runs outside it: a `break` there leaves the block.
        found = [n for stmt in node.body for n in _exits(stmt, True)]
        return found + [n for stmt in node.orelse for n in _exits(stmt, in_loop)]
    return [n for child in ast.iter_child_nodes(node) for n in _exits(child, in_loop)]


def _finally_exits(source: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(source)):
        for stmt in getattr(node, "finalbody", []):
            lines += [exit_.lineno for exit_ in _exits(stmt, False)]
    return sorted(lines)


def test_the_check_finds_what_python_warns_on():
    source = (
        "def f(writer):\n"
        "    try:\n"
        "        pass\n"
        "    finally:\n"
        "        try:\n"
        "            writer.close()\n"
        "        except ConnectionError:\n"
        "            return\n"
        "        for item in ():\n"
        "            break\n"
        "        def inner():\n"
        "            return 1\n"
    )
    assert _finally_exits(source) == [8]


def test_no_sdk_module_leaves_a_finally_block():
    package = Path(naas_abi_sdk.__file__).parent
    found = [
        f"{path.relative_to(package)}:{line}"
        for path in sorted(package.rglob("*.py"))
        for line in _finally_exits(path.read_text(encoding="utf-8"))
    ]
    assert found == []
