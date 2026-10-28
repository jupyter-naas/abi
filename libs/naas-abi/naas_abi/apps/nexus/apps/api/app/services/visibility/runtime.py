"""Where ``authz`` finds the workspace's visibility. The API installs the
database's at start (``factory.install``); without one (a route tested alone)
nothing is hidden. Tests install their own with ``configure``."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.visibility.service import WorkspaceVisibility

_current: WorkspaceVisibility | None = None


def configure(visibility: WorkspaceVisibility | None) -> WorkspaceVisibility | None:
    """Install ``visibility`` (None: nothing hidden); returns the previous one."""
    global _current
    previous = _current
    _current = visibility
    return previous


def current() -> WorkspaceVisibility | None:
    return _current
