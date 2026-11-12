"""What the source control service accepts as a repository segment, a file
path, a branch or ref, a commit and a forge username.

Each value names something inside one repository, whatever adapter serves it:
the forge puts them in API URLs, the local adapter in file paths and git
arguments. A value that could name something else (a dot segment, a query or
fragment, a control character, an option) is refused here, before any adapter
sees it.
"""

from __future__ import annotations

import re

# One path segment of a repository id (owner, name).
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# A forge username: Forgejo's alphabet, starting with a letter or a digit.
_USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
# A commit id: an abbreviated or full SHA-1 or SHA-256.
_COMMIT = re.compile(r"[0-9a-fA-F]{7,64}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# Never in a file path: they end the URL path or separate segments elsewhere.
_PATH_FORBIDDEN = frozenset("?#\\")
# Never in a ref: git's own rules (``git check-ref-format``), plus ``#``.
_REF_FORBIDDEN = frozenset(" ~^:?*[\\#")
_MAX_REF = 255
_MAX_PATH = 4096


def segment_ok(value: object) -> bool:
    """One segment of a repository id: letters, digits, ``.``, ``_``, ``-``,
    starting with a letter or a digit."""
    return (
        isinstance(value, str)
        and bool(_SEGMENT.fullmatch(value))
        and value not in (".", "..")
    )


def repo_id_ok(repo_id: object) -> bool:
    """``<owner>/<name>`` of two plain segments."""
    if not isinstance(repo_id, str):
        return False
    owner, sep, name = repo_id.partition("/")
    return bool(sep) and segment_ok(owner) and segment_ok(name)


def path_segments(path: str) -> list[str] | None:
    """The segments of a file path inside a repository, or None when it is not
    one. A leading ``/`` (the repository root) and a trailing ``/`` (a
    directory) are accepted; the root itself is the empty list."""
    if not isinstance(path, str) or len(path) > _MAX_PATH:
        return None
    if _CONTROL.search(path) or any(c in _PATH_FORBIDDEN for c in path):
        return None
    inner = path.strip("/")
    if not inner:
        return []
    segments = inner.split("/")
    for segment in segments:
        if segment in ("", ".", "..") or segment.lower() == ".git":
            return None
    return segments


def file_path_ok(path: object, *, root_ok: bool = False) -> bool:
    """A file or directory inside the repository's tree, never its ``.git``.
    ``root_ok`` accepts the repository root (``""`` or ``/``)."""
    segments = path_segments(path) if isinstance(path, str) else None
    if segments is None:
        return False
    return bool(segments) or root_ok


def ref_ok(ref: object) -> bool:
    """A branch or tag name, or a commit id, by git's rules: never an option,
    a dot segment, a range or a revision expression."""
    if not isinstance(ref, str) or not ref or len(ref) > _MAX_REF:
        return False
    if _CONTROL.search(ref) or any(c in _REF_FORBIDDEN for c in ref):
        return False
    if ref.startswith(("-", "/")) or ref.endswith(("/", ".", ".lock")):
        return False
    if ".." in ref or "//" in ref or "@{" in ref or ref == "@":
        return False
    return all(
        segment and not segment.startswith(".") and not segment.endswith(".lock")
        for segment in ref.split("/")
    )


def commit_ok(sha: object) -> bool:
    """A commit id (7 to 64 hexadecimal digits)."""
    return isinstance(sha, str) and bool(_COMMIT.fullmatch(sha))


def username_ok(username: object) -> bool:
    """A forge username: one plain segment."""
    return (
        isinstance(username, str)
        and bool(_USERNAME.fullmatch(username))
        and ".." not in username
    )
