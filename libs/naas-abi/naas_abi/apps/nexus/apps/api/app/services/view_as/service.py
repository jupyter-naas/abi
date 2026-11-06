"""View as: an administrator sees Nexus as another person, in one workspace.

The use cases of the view. Who may view as whom is IAM's (``iam:ViewAs`` and the
rule that the person holds no more than the viewer): this service asks, in the
viewer's name, and adds no role check. It keeps the view (one per session, 15
minutes at most), audits every start, stop and refusal, and answers, at every
request, whether a session has a view running.

* **Start** is audited first (``run_audited``, the IAM admin's fail-closed log):
  no start record, no view. A refusal is a record too.
* **A view ends** at Stop, at sign-out, at its end time, or when IAM no longer
  accepts it. The end is recorded when the server sees it.
* **Groups.** The person's identity provider groups are the ones their most recent
  sign-in session recorded; the view keeps exactly the groups IAM checked.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
    AuditRecord,
    AuditUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import run_audited
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import (
    EXPIRED,
    NO_LONGER_ALLOWED,
    STOP,
    VIEW_LIFETIME,
    Person,
    UnknownPersonError,
    UnknownWorkspaceError,
    ViewAlreadyRunningError,
    Viewer,
    ViewIam,
    ViewRecord,
    ViewStore,
    WorkspaceRef,
)

_log = logging.getLogger(__name__)

SERVICE = "iam"
START = "view_as_start"
END = "view_as_stop"


def now_naive() -> datetime:
    from datetime import UTC

    return datetime.now(UTC).replace(tzinfo=None)


class ViewAsService:
    def __init__(
        self,
        store: ViewStore,
        iam: ViewIam,
        audit: AdminAuditLog,
        *,
        clock: Callable[[], datetime] = now_naive,
        lifetime: timedelta = VIEW_LIFETIME,
    ) -> None:
        self._store = store
        self._iam = iam
        self._audit = audit
        self._clock = clock
        self._lifetime = lifetime

    # -- who may be viewed where --------------------------------------------------

    async def workspaces(self, viewer: Viewer, principal_id: str) -> list[WorkspaceRef]:
        """The workspaces the person belongs to where IAM accepts a view by the
        viewer; none for a person who has not signed in to Nexus."""
        person = await self._store.person(principal_id)
        if person is None:
            return []
        groups, _ = await self._groups(person)
        found = []
        for workspace in await self._store.workspaces(await self._iam.candidates(person.user_id)):
            container = await self._iam.container_of(workspace.id)
            if container is None:
                continue
            verdict = await self._iam.verdict(viewer, principal_id, container, groups)
            if verdict.allowed:
                found.append(workspace)
        return found

    async def _groups(self, person: Person) -> tuple[tuple[str, ...], datetime | None]:
        recorded = await self._store.recorded_groups(person.user_id)
        return (recorded.group_ids, recorded.at) if recorded is not None else ((), None)

    # -- start and stop -----------------------------------------------------------

    async def start(self, viewer: Viewer, principal_id: str, workspace_id: str) -> ViewRecord:
        """Start the session's view of ``principal_id`` in ``workspace_id``: IAM's
        ``require_view_as`` decides (``ViewAsRefused`` carries its message). The
        start is audited first; a refusal and a failure are records too."""
        started = self._clock()
        ends_at = started + self._lifetime
        person = await self._store.person(principal_id)
        groups, groups_from = await self._groups(person) if person else ((), None)
        source = f"recorded at {groups_from.isoformat()}" if groups_from else "none"
        detail = f"workspace {workspace_id}; ends {ends_at.isoformat()}; identity provider groups: {source}"
        action = AdminAction(viewer.user_id, SERVICE, START, principal_id, detail)

        async def make() -> ViewRecord:
            if person is None:
                raise UnknownPersonError()
            await self._end_if_over(viewer.session_id)
            workspace = next(iter(await self._store.workspaces([workspace_id])), None)
            container = await self._iam.container_of(workspace_id) if workspace else None
            if workspace is None or container is None:
                raise UnknownWorkspaceError()
            await self._iam.require(viewer, principal_id, container, groups)
            record = ViewRecord(
                session_id=viewer.session_id,
                viewer_id=viewer.user_id,
                person_id=person.user_id,
                person_principal_id=person.principal_id,
                person_name=person.name,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                container=container,
                group_ids=groups,
                groups_from=groups_from,
                started_at=started,
                ends_at=ends_at,
            )
            if not await self._store.begin(record):
                await self._store.commit()
                raise ViewAlreadyRunningError()
            await self._store.commit()
            return record

        return await run_audited(self._audit, action, make)

    async def stop(self, session_id: str, reason: str = STOP) -> ViewRecord | None:
        """End the session's running view and record it; None when none runs."""
        record = await self._store.get(session_id)
        if record is None or record.ended_at is not None:
            return None
        return await self._end(record, reason)

    async def _end(self, record: ViewRecord, reason: str) -> ViewRecord | None:
        ended = self._clock()
        if not await self._store.end(record.session_id, ended):
            await self._store.commit()
            return None  # another request ended it first, and recorded it
        await self._store.commit()
        action = AdminAction(record.viewer_id, SERVICE, END, record.person_principal_id, reason)
        try:
            # The end happened: a record that cannot be written never keeps a view open.
            await self._audit.record(AuditRecord(action, "succeeded"))
        except AuditUnavailable as exc:
            _log.warning("view as: the end of a view could not be recorded: %s", exc.reason)
        return replace(record, ended_at=ended)

    async def _end_if_over(self, session_id: str) -> None:
        """Record the end of the session's view when its time has come."""
        record = await self._store.get(session_id)
        if record is not None and record.ended_at is None and record.ends_at <= self._clock():
            await self._end(record, EXPIRED)

    # -- at every request ---------------------------------------------------------

    async def running(self, session_id: str) -> ViewRecord | None:
        """The session's view if it is running now: not ended, not past its end.
        Reads only, and records nothing."""
        record = await self._store.get(session_id)
        if record is None or record.ended_at is not None or record.ends_at <= self._clock():
            return None
        return record

    async def resolve(self, viewer: Viewer) -> ViewRecord | None:
        """The view a request of the session runs in, or None: it runs as the
        viewer. A view past its end is ended (recorded "expired"), and one IAM no
        longer accepts (``iam:ViewAs`` is decided again here, with the groups
        checked at the start) is ended too."""
        record = await self._store.get(viewer.session_id)
        if record is None or record.ended_at is not None or record.viewer_id != viewer.user_id:
            return None
        if record.ends_at <= self._clock():
            await self._end(record, EXPIRED)
            return None
        if not await self._iam.allows(viewer, record.person_principal_id, record.container):
            await self._end(record, NO_LONGER_ALLOWED)
            return None
        return record
