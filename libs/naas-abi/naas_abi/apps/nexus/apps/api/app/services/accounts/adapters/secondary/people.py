"""The platform's people (``services/people``), as the accounts' directory invites
someone: an account with no role, made on the inviting user's own right."""

from __future__ import annotations

from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.services.accounts.port import Created, PeopleGateway
from naas_abi.apps.nexus.apps.api.app.services.people.service import PeopleService


class PeopleAdapter(PeopleGateway):
    def __init__(self, service: PeopleService) -> None:
        self._service = service

    async def create(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        by: str,
        inviter_name: str | None,
    ) -> Created:
        result = await self._service.create_or_link(
            email=email,
            name=name,
            provider=provider,
            grant=None,
            by=SimpleNamespace(id=by, name=inviter_name or ""),
        )
        return Created(
            user_id=result.user.id,
            user_created=result.provisioned,
            sign_in_email_sent=result.sign_in_email_sent,
            provisioning_skipped=result.provisioning_skipped,
            warning=result.warning,
        )
