"""Fakes for the view's tests: a store in memory, and an IAM that says what a test tells it."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.view_as.port import (
    Person,
    RecordedGroups,
    Viewer,
    ViewIam,
    ViewRecord,
    ViewStore,
    WorkspaceRef,
)
from naas_abi_core.services.iam.IAMPorts import ViewAsRefused, ViewAsVerdict


class MemoryViewStore(ViewStore):
    def __init__(self) -> None:
        self.views: dict[str, ViewRecord] = {}
        self.people: dict[str, Person] = {}
        self.groups: dict[str, RecordedGroups] = {}
        self.workspace_rows: dict[str, WorkspaceRef] = {}

    async def get(self, session_id: str) -> ViewRecord | None:
        return self.views.get(session_id)

    async def begin(self, record: ViewRecord) -> bool:
        current = self.views.get(record.session_id)
        if current is not None and current.ended_at is None:
            return False
        self.views[record.session_id] = record
        return True

    async def end(self, session_id: str, at: datetime) -> bool:
        current = self.views.get(session_id)
        if current is None or current.ended_at is not None:
            return False
        self.views[session_id] = replace(current, ended_at=at)
        return True

    async def person(self, principal_id: str) -> Person | None:
        return self.people.get(principal_id)

    async def recorded_groups(self, user_id: str) -> RecordedGroups | None:
        return self.groups.get(user_id)

    async def workspaces(self, ids: list[str]) -> list[WorkspaceRef]:
        return [self.workspace_rows[i] for i in ids if i in self.workspace_rows]

    async def commit(self) -> None:
        return None


class FakeViewIam(ViewIam):
    """Allows what ``allowed`` holds: ``(principal_id, container)`` pairs; refuses the
    rest as IAM does. ``checked`` remembers what it was asked, and ``groups`` the groups."""

    def __init__(self) -> None:
        self.allowed: set[tuple[str, str]] = set()
        self.containers: dict[str, str] = {}
        self.belongs: dict[str, list[str]] = {}
        self.checked: list[tuple[str, str]] = []
        self.groups: list[tuple[str, ...]] = []
        self.one_check = 0

    async def candidates(self, user_id: str) -> list[str]:
        return self.belongs.get(user_id, [])

    async def container_of(self, workspace_id: str) -> str | None:
        return self.containers.get(workspace_id)

    def _verdict(self, principal_id: str, container: str) -> ViewAsVerdict:
        if (principal_id, container) in self.allowed:
            return ViewAsVerdict(allowed=True)
        return ViewAsVerdict(
            allowed=False,
            code="not_allowed",
            reason=f"You may not view as {principal_id} in {container}",
        )

    async def verdict(
        self, viewer: Viewer, principal_id: str, container: str, groups: tuple[str, ...]
    ) -> ViewAsVerdict:
        self.groups.append(groups)
        return self._verdict(principal_id, container)

    async def require(
        self, viewer: Viewer, principal_id: str, container: str, groups: tuple[str, ...]
    ) -> None:
        self.checked.append((principal_id, container))
        self.groups.append(groups)
        verdict = self._verdict(principal_id, container)
        if not verdict.allowed:
            raise ViewAsRefused("", code=verdict.code or "", message=verdict.reason or "")

    async def allows(self, viewer: Viewer, principal_id: str, container: str) -> bool:
        self.one_check += 1
        return (principal_id, container) in self.allowed
