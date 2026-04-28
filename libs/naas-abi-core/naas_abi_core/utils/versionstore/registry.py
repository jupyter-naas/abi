"""StoreRegistry: manage multiple namespaced Store instances under one root.

Namespacing in versionstore is not a first-class Store concept; it's just
multiple Store instances rooted at different paths. This registry is a thin
convenience wrapper for that pattern.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator

from .store import Store


class StoreRegistry:
    """A directory of named Store instances.

    Example::

        registry = StoreRegistry("data/")
        users = registry.get("users")
        users.put(uid, payload)

    Each namespace is an independent Store with its own SQLite index and
    filesystem tree. They share nothing.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, name: str) -> Store:
        """Return the Store for namespace `name`, creating it if missing."""
        self._validate(name)
        return Store(self.root / name)

    def exists(self, name: str) -> bool:
        self._validate(name)
        return (self.root / name).is_dir()

    def list(self) -> Iterator[str]:
        """Yield the names of all existing namespaces."""
        if not self.root.exists():
            return
        for p in self.root.iterdir():
            if p.is_dir():
                yield p.name

    def drop(self, name: str) -> None:
        """Irrevocably delete a namespace and all its revisions.

        This is an escape hatch (e.g. for GDPR erasure). Normal operation is
        append-only; `drop` breaks that property deliberately.
        """
        self._validate(name)
        path = self.root / name
        if path.exists():
            shutil.rmtree(path)

    @staticmethod
    def _validate(name: str) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("namespace name must be a non-empty string")
        if "/" in name or "\\" in name or "\0" in name or name in (".", ".."):
            raise ValueError(f"Invalid namespace name: {name!r}")
