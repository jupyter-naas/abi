"""Secondary port: where a workspace's saved graph views are kept.

The store only loads and saves views. Which views a user sees, how folders are
derived from paths and what a folder move rewrites are ``ViewService``'s.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GraphViewRecord:
    id: str
    workspace_id: str
    name: str
    graph_id: str
    graph_uri: str
    description: str | None = None
    view_type: str = "network"
    kind: str = "network"
    visibility: str = "workspace"
    creator_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    path: str = ""
    # Set by the store: when the view was added, and last saved (naive UTC).
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphViewStorePort(ABC):
    @abstractmethod
    async def list(self, workspace_id: str) -> list[GraphViewRecord]:
        """Every view of the workspace, whoever created it, in no particular order."""

    @abstractmethod
    async def get(self, workspace_id: str, view_id: str) -> GraphViewRecord | None:
        """The view, if it belongs to the workspace."""

    @abstractmethod
    async def add(self, view: GraphViewRecord) -> GraphViewRecord:
        """Store a new view; returns it with ``created_at`` and ``updated_at`` set."""

    @abstractmethod
    async def save(self, view: GraphViewRecord) -> GraphViewRecord | None:
        """Replace a stored view's fields (``created_at`` kept, ``updated_at`` set).
        Returns None when the workspace has no view with that id."""

    @abstractmethod
    async def delete(self, workspace_id: str, view_id: str) -> bool:
        """Remove the view. Returns False when the workspace has none with that id."""

    @abstractmethod
    async def move(self, workspace_id: str, paths: dict[str, str]) -> None:
        """Set the path of each view named in ``paths`` (view id → new path), all or
        none. Ids the workspace does not hold are ignored."""
