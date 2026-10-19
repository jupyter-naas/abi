"""Build the invitation service, from the engine's services; tests replace the
runtime with ``configure``."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.engine import (
    EngineDirectoryGateway,
    EngineGrantsGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.mailer import (
    EngineInvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.postgres import (
    InvitationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import InvitationMailer
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    default_iam,
    default_identity,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


def now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def sign_in_url(email: str, provider: str) -> str:
    """Where the invitee signs in: the web app's login, with their address."""
    base = settings.frontend_url.rstrip("/")
    return f"{base}/auth/login?{urlencode({'email': email, 'provider': provider})}"


class InvitationRuntime:
    def __init__(
        self,
        identity: Callable[[], Any | None] = default_identity,
        iam: Callable[[], Any | None] = default_iam,
        mailer: InvitationMailer | None = None,
    ) -> None:
        self.directory = EngineDirectoryGateway(identity)
        self.grants = EngineGrantsGateway(iam)
        self.mailer = mailer or EngineInvitationMailer()

    def claimer(self, db: AsyncSession) -> Callable[[Any, Any], Awaitable[None]]:
        """What a sign-in runs for its user: the memberships of the invitations
        their verified email was sent."""
        service = self.service(db)

        async def claim(user: Any, signed_in: Any) -> None:
            token = signed_in.token
            # The provider vouched for the address, and Nexus stored it as
            # given: a placeholder for an unverified one never matches anyone.
            if not token.email or not token.email_verified:
                return
            if token.email.lower() != user.email.lower():
                return
            await service.claim(user_id=user.id, email=user.email, provider=token.provider)

        return claim

    def service(self, db: AsyncSession) -> InvitationService:
        return InvitationService(
            InvitationSecondaryAdapterPostgres(db),
            self.directory,
            self.grants,
            self.mailer,
            sign_in_url=sign_in_url,
            clock=now_naive,
        )


RUNTIME = InvitationRuntime()


def configure(runtime: InvitationRuntime) -> InvitationRuntime:
    """Replace the runtime (tests); returns the previous one."""
    global RUNTIME
    previous, RUNTIME = RUNTIME, runtime
    return previous


def get_invitation_service(db: AsyncSession = Depends(get_db)) -> InvitationService:
    """The invitation service of a request (a route dependency)."""
    return RUNTIME.service(db)
