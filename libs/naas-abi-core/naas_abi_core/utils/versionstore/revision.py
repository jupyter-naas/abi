"""Revision: a single immutable version of a uid's payload."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


HASH_LEN = 64  # SHA-256 hex length
TS_DIGITS = 20  # zero-padded nanosecond timestamp
DEFAULT_BRANCH = "main"


@dataclass(frozen=True)
class Revision:
    """A single revision of a uid on a branch.

    The on-disk filename is one of:

    - ``{ts_ns:020d}.{prev_hash}.{content_hash}``                 — main branch
    - ``{ts_ns:020d}.{prev_hash}.{content_hash}.{branch}``        — other branches

    Keeping the 3-part form for ``main`` preserves backward compatibility with
    pre-branching stores: their existing files parse unchanged.

    ``prev_hash`` is the content_hash of the previous revision for this uid on
    this branch, or ``"0" * 64`` (GENESIS) for the first revision on the branch.
    """

    uid: str
    ts_ns: int
    prev_hash: str
    content_hash: str
    path: Path
    branch: str = DEFAULT_BRANCH

    @property
    def timestamp(self) -> datetime:
        """The revision timestamp as a timezone-aware UTC datetime."""
        return datetime.fromtimestamp(self.ts_ns / 1_000_000_000, tz=timezone.utc)

    @property
    def filename(self) -> str:
        base = f"{self.ts_ns:0{TS_DIGITS}d}.{self.prev_hash}.{self.content_hash}"
        if self.branch == DEFAULT_BRANCH:
            return base
        return f"{base}.{self.branch}"

    def read(self) -> bytes:
        """Read the payload bytes from disk."""
        return self.path.read_bytes()

    @classmethod
    def parse_filename(cls, uid: str, filename: str, dir_path: Path) -> "Revision":
        """Parse a revision filename. Raises ValueError if malformed.

        Accepts both the legacy 3-part form (defaults to ``main``) and the
        4-part form ``ts.prev.content.branch``.
        """
        parts = filename.split(".")
        if len(parts) == 3:
            ts_str, prev_hash, content_hash = parts
            branch = DEFAULT_BRANCH
        elif len(parts) == 4:
            ts_str, prev_hash, content_hash, branch = parts
            if not branch:
                raise ValueError(f"Empty branch in filename: {filename!r}")
        else:
            raise ValueError(f"Invalid revision filename: {filename!r}")
        if len(prev_hash) != HASH_LEN or len(content_hash) != HASH_LEN:
            raise ValueError(f"Invalid hash length in filename: {filename!r}")
        if not ts_str.isdigit():
            raise ValueError(f"Invalid timestamp in filename: {filename!r}")
        return cls(
            uid=uid,
            ts_ns=int(ts_str),
            prev_hash=prev_hash,
            content_hash=content_hash,
            path=dir_path / filename,
            branch=branch,
        )
