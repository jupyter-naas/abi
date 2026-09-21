"""Read-only Nexus source tools for feature office agents.

Feature agents must explain how their feature is built from the code, not from
training data. The default ``read_file`` / ``list_dir`` tools reach the user's
Coder workspace through a sidecar, which is only bound on Slides and Code. On
Apps, Ontology, Graph, ... there is no sidecar, so these tools read the
installed packages directly.

Scope is two package roots and nothing else: ``naas_abi`` (Nexus API + web,
agents, ontologies) and ``naas_abi_core`` (engine ports and adapters: triple
store, datasets, coding environment, agents). Paths are resolved (symlinks
included) and must stay under a root. Secret-like files are refused and
generated trees are skipped. Paths are shown as ``naas_abi/...`` or
``naas_abi_core/...`` so answers cite the path a developer finds in the repo.

A pip-installed wheel only carries Python and packaged data; ``apps/web``
sources exist on editable/vendored installs. A missing web path says so
instead of looking like a typo.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PREFIX = "naas_abi"
_CORE_PREFIX = "naas_abi_core"
_WEB_PREFIX = "apps/nexus/apps/web"
# Longest name first so ``naas_abi_core/...`` never reads as ``naas_abi``.
_PREFIX_RE = re.compile(r"(?:^|/)(naas_abi_core|naas_abi)(?:/(.*))?$")
_DRIVE_RE = re.compile(r"^[A-Za-z]:/")


def _find_core_root() -> Path | None:
    spec = importlib.util.find_spec(_CORE_PREFIX)
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve().parent


CORE_ROOT = _find_core_root()

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".turbo",
        ".venv",
        "__pycache__",
        "coverage",
        "node_modules",
    }
)
_SECRET_SUFFIXES = frozenset({".key", ".p12", ".pem", ".pfx", ".db", ".sqlite"})
_SECRET_NAMES = frozenset({"credentials.json", "id_ed25519", "id_rsa"})
_TEXT_SUFFIXES = frozenset(
    {
        ".css",
        ".html",
        ".js",
        ".json",
        ".jsx",
        ".md",
        ".mjs",
        ".py",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".ttl",
        ".txt",
        ".yaml",
        ".yml",
    }
)
_MAX_READ_BYTES = 2_000_000
_MAX_SEARCH_BYTES = 1_000_000
_MAX_READ_LINES = 800
_MAX_LIST_ENTRIES = 400
_MAX_SEARCH_RESULTS = 100
_MAX_SEARCH_FILES = 20_000
_MAX_LINE_CHARS = 300


class SourcePathError(ValueError):
    """Path is outside the packages, secret-like, or otherwise refused."""


_OUTSIDE = "is outside naas_abi and naas_abi_core. Only the Nexus/ABI package source is readable."


def _roots() -> dict[str, Path]:
    roots = {_DEFAULT_PREFIX: PACKAGE_ROOT}
    if CORE_ROOT is not None:
        roots[_CORE_PREFIX] = CORE_ROOT
    return roots


def _root_for(path: Path) -> tuple[str, Path] | None:
    """(prefix, root) that contains ``path``; the deepest root wins."""
    hits = [
        (prefix, root)
        for prefix, root in _roots().items()
        if path == root or root in path.parents
    ]
    return max(hits, key=lambda hit: len(hit[1].parts)) if hits else None


def _display(path: Path) -> str:
    found = _root_for(path)
    if found is None:
        return path.name
    prefix, root = found
    rel = path.relative_to(root).as_posix()
    return prefix if rel == "." else f"{prefix}/{rel}"


def _split_input(raw: str) -> tuple[str, str]:
    """(root prefix, relative path) for ``naas_abi/...``, ``naas_abi_core/...``,
    repo paths like ``libs/naas-abi/naas_abi/...``, or naas_abi-relative paths.

    An absolute path that does not go through a package folder is outside by
    definition.
    """
    text = (raw or "").strip().replace("\\", "/")
    match = _PREFIX_RE.search(text.rstrip("/"))
    if match:
        return match.group(1), (match.group(2) or "").strip("/")
    if text.startswith("/") or _DRIVE_RE.match(text):
        raise SourcePathError(f"'{raw}' {_OUTSIDE}")
    return _DEFAULT_PREFIX, text.strip("/")


def _is_secret_like(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith(".env") and not name.endswith(".example"):
        return True
    return name in _SECRET_NAMES or path.suffix.lower() in _SECRET_SUFFIXES


def resolve_source_path(raw: str) -> Path:
    """Package path for ``raw``; raises SourcePathError when refused."""
    prefix, rel = _split_input(raw)
    root = _roots().get(prefix)
    if root is None:
        raise SourcePathError(f"'{raw}': {prefix} is not installed here.")
    candidate = (root / rel).resolve()
    if candidate != root and root not in candidate.parents:
        raise SourcePathError(f"'{raw}' {_OUTSIDE}")
    if _is_secret_like(candidate):
        raise SourcePathError(
            f"'{raw}' looks like a secret or data file. Not readable."
        )
    return candidate


def _missing(raw: str, path: Path) -> dict[str, str]:
    web = PACKAGE_ROOT / _WEB_PREFIX
    if (path == web or web in path.parents) and not web.is_dir():
        return {
            "error": (
                "The Nexus web sources (apps/nexus/apps/web) are not shipped in "
                "this deployment. Answer from the API side and say the web files "
                "were not available."
            )
        }
    return {"error": f"'{raw}' does not exist. Use list_nexus_source to browse."}


def list_source_dir(path: str = "naas_abi/apps/nexus/apps") -> dict[str, Any]:
    target = resolve_source_path(path)
    if not target.exists():
        return _missing(path, target)
    if not target.is_dir():
        return {"error": f"'{path}' is a file. Use read_nexus_source."}
    dirs: list[str] = []
    files: list[dict[str, Any]] = []
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries[:_MAX_LIST_ENTRIES]:
        if entry.is_dir():
            if entry.name not in _SKIP_DIRS:
                dirs.append(entry.name + "/")
        elif not _is_secret_like(entry):
            files.append({"name": entry.name, "bytes": entry.stat().st_size})
    return {
        "path": _display(target),
        "dirs": dirs,
        "files": files,
        "truncated": len(entries) > _MAX_LIST_ENTRIES,
    }


def read_source_file(
    path: str, start_line: int = 1, max_lines: int = 400
) -> dict[str, Any]:
    target = resolve_source_path(path)
    if not target.exists():
        return _missing(path, target)
    if target.is_dir():
        return {"error": f"'{path}' is a folder. Use list_nexus_source."}
    size = target.stat().st_size
    if size > _MAX_READ_BYTES:
        return {"error": f"'{path}' is {size} bytes. Use search_nexus_source on it."}
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(start_line or 1))
    count = max(1, min(int(max_lines or 400), _MAX_READ_LINES))
    window = lines[start - 1 : start - 1 + count]
    end = start + len(window) - 1
    return {
        "path": _display(target),
        "start_line": start,
        "end_line": end,
        "total_lines": len(lines),
        "more": end < len(lines),
        "content": "\n".join(
            f"{number:>5}  {text}" for number, text in enumerate(window, start=start)
        ),
    }


def _compile(pattern: str, ignore_case: bool) -> re.Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(pattern, flags)
    except re.error:
        return re.compile(re.escape(pattern), flags)


def search_source(
    pattern: str,
    path: str = "naas_abi/apps/nexus/apps",
    glob: str = "",
    ignore_case: bool = False,
    max_results: int = 50,
) -> dict[str, Any]:
    if not (pattern or "").strip():
        return {"error": "pattern is required."}
    target = resolve_source_path(path)
    if not target.exists():
        return _missing(path, target)
    regex = _compile(pattern, ignore_case)
    limit = max(1, min(int(max_results or 50), _MAX_SEARCH_RESULTS))
    name_glob = (glob or "").strip()
    matches: list[dict[str, Any]] = []
    scanned = 0
    walker: Any = (
        [(str(target.parent), [], [target.name])]
        if target.is_file()
        else os.walk(target)
    )
    for dirpath, dirnames, filenames in walker:
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for filename in sorted(filenames):
            file_path = Path(dirpath) / filename
            if file_path.suffix.lower() not in _TEXT_SUFFIXES or _is_secret_like(
                file_path
            ):
                continue
            # os.walk does not follow symlinked dirs, but read_text follows a
            # symlinked file. Keep the package-root confinement for those too.
            if _root_for(file_path.resolve()) is None:
                continue
            display = _display(file_path)
            if name_glob and not (
                fnmatch.fnmatch(filename, name_glob)
                or fnmatch.fnmatch(display, name_glob)
            ):
                continue
            try:
                if file_path.stat().st_size > _MAX_SEARCH_BYTES:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            scanned += 1
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    matches.append(
                        {
                            "path": display,
                            "line": number,
                            "text": line.strip()[:_MAX_LINE_CHARS],
                        }
                    )
                    if len(matches) >= limit:
                        return {
                            "matches": matches,
                            "truncated": True,
                            "files_scanned": scanned,
                        }
            if scanned >= _MAX_SEARCH_FILES:
                return {"matches": matches, "truncated": True, "files_scanned": scanned}
    return {"matches": matches, "truncated": False, "files_scanned": scanned}


def _guarded(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except SourcePathError as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"Could not read source: {exc.strerror or type(exc).__name__}"}


def nexus_source_tools() -> list[BaseTool]:
    @tool
    def list_nexus_source(path: str = "naas_abi/apps/nexus/apps") -> dict[str, Any]:
        """List a folder of the Nexus/ABI source (read-only).

        Paths look like naas_abi/apps/nexus/apps/api/app/services/apps (Nexus)
        or naas_abi_core/services/triple_store (engine ports and adapters).
        Generated folders are hidden.
        """
        return _guarded(list_source_dir, path)

    @tool
    def read_nexus_source(
        path: str, start_line: int = 1, max_lines: int = 400
    ) -> dict[str, Any]:
        """Read a Nexus/ABI source file (read-only) with line numbers.

        Use it before explaining how a feature is built. Cite the path and the
        lines you read. Page long files with start_line (max 800 lines per call).
        """
        return _guarded(
            read_source_file, path, start_line=start_line, max_lines=max_lines
        )

    @tool
    def search_nexus_source(
        pattern: str,
        path: str = "naas_abi/apps/nexus/apps",
        glob: str = "",
        ignore_case: bool = False,
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Search the Nexus/ABI source for a regex or literal (read-only).

        Returns path, line, and text per match. Narrow with path (a folder or
        file) and glob (e.g. "*.py", "*.tsx"). Use it to find where a route,
        component, store, or function is defined.
        """
        return _guarded(
            search_source,
            pattern,
            path=path,
            glob=glob,
            ignore_case=ignore_case,
            max_results=max_results,
        )

    return [list_nexus_source, read_nexus_source, search_nexus_source]
