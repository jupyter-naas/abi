"""Build the accounts' service of a request from the engine's IAM and identity,
Nexus's database, invitations and the IAM admin's audit log; tests ``configure``
another runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.secondary.engine import (
    EngineAccessGateway,
    EngineIdentityGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.secondary.invitations import (
    InvitationsAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.secondary.postgres import (
    AccountStorePostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    AccessGateway,
    IdentityGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.service import AccountService
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import AUDIT_PREFIX
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    default_identity,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.sql_audit_log import (
    SqlAdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AdminAuditLog
from sqlalchemy.ext.asyncio import AsyncSession


def now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _audit() -> AdminAuditLog:
    from naas_abi.apps.nexus.apps.api.app.core import database

    # The IAM admin's rows (``iam.``): Roles & permissions > Audit shows them.
    return SqlAdminAuditLog(lambda: database.async_engine, prefix=AUDIT_PREFIX)


class AccountRuntime:
    def __init__(
        self,
        identity: Callable[[], Any | None] = default_identity,
        *,
        access: AccessGateway | None = None,
        identity_gateway: IdentityGateway | None = None,
        audit: Callable[[], AdminAuditLog] = _audit,
    ) -> None:
        self.access = access or EngineAccessGateway()
        self.identity = identity_gateway or EngineIdentityGateway(identity)
        self._audit = audit

    def service(self, db: AsyncSession) -> AccountService:
        return AccountService(
            AccountStorePostgres(db),
            self.access,
            self.identity,
            InvitationsAdapter(invites_runtime.RUNTIME.service(db)),
            self._audit(),
            clock=now_naive,
        )


RUNTIME = AccountRuntime()


def configure(runtime: AccountRuntime) -> AccountRuntime:
    """Replace the runtime (tests); returns the previous one."""
    global RUNTIME
    previous, RUNTIME = RUNTIME, runtime
    return previous


def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    """The accounts' service of a request (a route dependency)."""
    return RUNTIME.service(db)
