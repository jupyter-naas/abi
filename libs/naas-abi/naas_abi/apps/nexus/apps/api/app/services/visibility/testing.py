"""A workspace visibility for tests: install one over in-memory readers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from naas_abi.apps.nexus.apps.api.app.services.visibility import runtime
from naas_abi.apps.nexus.apps.api.app.services.visibility.port import VisibilityReaderPort
from naas_abi.apps.nexus.apps.api.app.services.visibility.service import WorkspaceVisibility


@contextmanager
def visibility_installed(readers: Mapping[str, VisibilityReaderPort]) -> Iterator[None]:
    """``authz`` refuses what ``readers`` say a workspace turned off."""
    previous = runtime.configure(WorkspaceVisibility(readers))
    try:
        yield
    finally:
        runtime.configure(previous)
