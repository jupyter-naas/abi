"""Build the people service of a request from the engine's identity and IAM,
Nexus's database and the mail; tests ``configure`` another runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.invites.runtime import sign_in_url
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    default_iam,
    default_identity,
)
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.engine import (
    EngineAccessGateway,
    EngineIdentityGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.mailer import (
    EnginePeopleMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.postgres import (
    PeopleSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AccessGateway,
    IdentityGateway,
    PeopleMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import PeopleService
from sqlalchemy.ext.asyncio import AsyncSession


def now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PeopleRuntime:
    def __init__(
        self,
        identity: Callable[[], Any | None] = default_identity,
        iam: Callable[[], Any | None] = default_iam,
        *,
        identity_gateway: IdentityGateway | None = None,
        access: AccessGateway | None = None,
        mailer: PeopleMailer | None = None,
    ) -> None:
        self.identity = identity_gateway or EngineIdentityGateway(identity)
        self.access = access or EngineAccessGateway(iam)
        self.mailer = mailer or EnginePeopleMailer(sign_in_url=sign_in_url)

    def service(self, db: AsyncSession) -> PeopleService:
        return PeopleService(
            PeopleSecondaryAdapterPostgres(db),
            self.identity,
            self.access,
            self.mailer,
            clock=now_naive,
        )


RUNTIME = PeopleRuntime()


def configure(runtime: PeopleRuntime) -> PeopleRuntime:
    """Replace the runtime (tests); returns the previous one."""
    global RUNTIME
    previous, RUNTIME = RUNTIME, runtime
    return previous


def get_people_service(db: AsyncSession = Depends(get_db)) -> PeopleService:
    """The people service of a request (a route dependency)."""
    return RUNTIME.service(db)
