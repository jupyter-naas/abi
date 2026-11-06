"""Ports of "View as": the record of a view, what the view needs of Nexus's
database and of IAM, and the errors the service raises."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

from naas_abi_core.services.iam.IAMPorts import ViewAsVerdict

# How long a view lasts at most: the one place it is said.
VIEW_LIFETIME = timedelta(minutes=15)

# Why a view ended (the audit detail of ``iam.view_as_stop``).
STOP = "stop"
SIGN_OUT = "sign-out"
EXPIRED = "expired"
NO_LONGER_ALLOWED = "no longer allowed"


@dataclass(frozen=True)
class Viewer:
    """Who starts, stops or runs a view: the signed-in user of a cookie session,
    with the IAM groups that session maps to (they decide ``iam:ViewAs``)."""

    user_id: str
    session_id: str
    group_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Person:
    """Who a view shows: the Nexus user, and the IAM principal that is theirs."""

    user_id: str
    principal_id: str
    name: str


@dataclass(frozen=True)
class WorkspaceRef:
    id: str
    name: str
    organization_id: str | None
    organization_name: str | None


@dataclass(frozen=True)
class RecordedGroups:
    """The IAM groups the person's most recent sign-in session recorded."""

    group_ids: tuple[str, ...]
    at: datetime


@dataclass(frozen=True)
class ViewRecord:
    """A view: one per session, ended (``ended_at``) with Stop, the sign-out or its end time."""

    session_id: str
    viewer_id: str
    person_id: str
    person_principal_id: str
    person_name: str
    workspace_id: str
    workspace_name: str
    container: str
    group_ids: tuple[str, ...]
    groups_from: datetime | None
    started_at: datetime
    ends_at: datetime
    ended_at: datetime | None = None


class ViewAsError(Exception):
    """A view that cannot start or run: ``status`` is the HTTP answer."""

    status = 400


class UnknownPersonError(ViewAsError):
    status = 404

    def __init__(self) -> None:
        super().__init__("No such person: they have not signed in to Nexus")


class UnknownWorkspaceError(ViewAsError):
    status = 404

    def __init__(self) -> None:
        super().__init__("No such workspace")


class ViewAlreadyRunningError(ViewAsError):
    status = 409

    def __init__(self) -> None:
        super().__init__("A view is already running: stop it before starting another")


class ViewStore(ABC):
    """What a view keeps and reads in Nexus's database."""

    @abstractmethod
    async def get(self, session_id: str) -> ViewRecord | None:
        """The session's view, running or ended, as stored now."""

    @abstractmethod
    async def begin(self, record: ViewRecord) -> bool:
        """Keep ``record`` as the session's view, replacing an ended one; False
        when the session already has one that has not ended (atomically)."""

    @abstractmethod
    async def end(self, session_id: str, at: datetime) -> bool:
        """End the session's view when it has not ended; whether this call did."""

    @abstractmethod
    async def person(self, principal_id: str) -> Person | None:
        """The Nexus user of an IAM principal (a person who never signed in to
        Nexus is none), or None for a deleted account."""

    @abstractmethod
    async def recorded_groups(self, user_id: str) -> RecordedGroups | None:
        """The groups of the user's most recent ``auth_sessions`` row, with its
        time; None for a user with no session."""

    @abstractmethod
    async def workspaces(self, ids: list[str]) -> list[WorkspaceRef]:
        """The workspaces among ``ids`` that exist, by name."""

    @abstractmethod
    async def commit(self) -> None: ...


class ViewIam(ABC):
    """What a view asks of IAM, as the viewer (``api`` on behalf of the viewer,
    with the groups of their session): who may view as whom is IAM's."""

    @abstractmethod
    async def candidates(self, user_id: str) -> list[str]:
        """The ids of the workspaces the person belongs to: a role held there, or
        an organization-wide one (an organization's owner or admin)."""

    @abstractmethod
    async def container_of(self, workspace_id: str) -> str | None:
        """The workspace's container as IAM registered it."""

    @abstractmethod
    async def verdict(
        self, viewer: Viewer, principal_id: str, container: str, groups: tuple[str, ...]
    ) -> ViewAsVerdict:
        """IAM's decision (``view_as_verdict``)."""

    @abstractmethod
    async def require(
        self, viewer: Viewer, principal_id: str, container: str, groups: tuple[str, ...]
    ) -> None:
        """IAM's ``require_view_as``: raises ``ViewAsRefused`` with its message."""

    @abstractmethod
    async def allows(self, viewer: Viewer, principal_id: str, container: str) -> bool:
        """``iam:ViewAs`` on the person in the container: the one check made at
        every request of a view."""
