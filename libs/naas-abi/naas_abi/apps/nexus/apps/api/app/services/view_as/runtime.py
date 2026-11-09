"""Build the view service, and answer what a request needs of it.

``RUNTIME`` reads the engine's IAM and Nexus's database and audit log; tests replace
it with ``configure`` (and set its clock)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TypeVar

from naas_abi.apps.nexus.apps.api.app.services.oidc.service import ActiveSession
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.sql_audit_log import (
    SqlAdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AdminAuditLog
from naas_abi.apps.nexus.apps.api.app.services.view_as.active import current_view
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.secondary.engine import (
    ViewAsSecondaryAdapterEngine,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.secondary.links import (
    ViewAsSecondaryAdapterLinks,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.secondary.sql import (
    ViewAsSecondaryAdapterSql,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import (
    SIGN_OUT,
    ViewEndedError,
    Viewer,
    ViewIam,
    ViewLinks,
    ViewRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.service import ViewAsService, now_naive
from naas_abi_core import logger
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

# The IAM admin's records and the view's are one history: ``iam.view_as_start``, ...
AUDIT_PREFIX = "iam."


def viewer_of(session: ActiveSession) -> Viewer:
    return Viewer(
        user_id=session.user_id, session_id=session.id, group_ids=tuple(session.group_ids)
    )


class ViewAsRuntime:
    def __init__(
        self,
        iam: ViewIam | None = None,
        audit: Callable[[], AdminAuditLog] | None = None,
        clock: Callable[[], datetime] = now_naive,
        links: ViewLinks | None = None,
    ) -> None:
        self.iam = iam or ViewAsSecondaryAdapterEngine()
        self.links = links or ViewAsSecondaryAdapterLinks()
        self._audit = audit or _default_audit
        self.clock = clock

    def service(self, db: AsyncSession) -> ViewAsService:
        return ViewAsService(
            ViewAsSecondaryAdapterSql(db),
            self.iam,
            self._audit(),
            clock=self.clock,
            links=self.links,
        )


def _default_audit() -> AdminAuditLog:
    from naas_abi.apps.nexus.apps.api.app.core import database

    return SqlAdminAuditLog(lambda: database.async_engine, prefix=AUDIT_PREFIX)


RUNTIME = ViewAsRuntime()


def configure(runtime: ViewAsRuntime) -> ViewAsRuntime:
    """Replace the runtime (tests); returns the previous one."""
    global RUNTIME
    previous, RUNTIME = RUNTIME, runtime
    return previous


async def running_view(session: ActiveSession) -> ViewRecord | None:
    """The view a request of this cookie session runs in, None when it runs as the
    viewer. An expired view is ended and recorded here. Raises when IAM or the
    database cannot say: the request then names nobody."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await RUNTIME.service(db).resolve(viewer_of(session))


async def is_viewing(session_id: str) -> bool:
    """Whether the session has a view running (the WebSocket handshake asks)."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await RUNTIME.service(db).running(session_id) is not None


async def end_on_sign_out(session: ActiveSession) -> None:
    """The sign-out ends the session's view; it never fails the sign-out."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await RUNTIME.service(db).stop(session.id, SIGN_OUT)
    except Exception as exc:  # noqa: BLE001 - the session is ended anyway, and with it the view
        logger.warning(f"The view of session {session.id} was not ended at sign-out: {exc}")


async def audited_open(app: str, make: Callable[[], Awaitable[T]]) -> T:
    """Make the link that opens ``app`` (``make``). In a view the open is audited
    (``iam.view_as_open_app``: the app, the person, the viewer) and fails closed, 503: no
    record, no link; outside one it is just ``make``."""
    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable

    view = current_view()
    if view is None:
        return await make()
    async with AsyncSessionLocal() as db:
        service = RUNTIME.service(db)
        try:
            return await service.open_app(view, app, make)
        except AuditUnavailable as exc:
            raise HTTPException(status_code=503, detail=f"No app opened: {exc}") from exc
        except ViewEndedError as exc:
            raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
