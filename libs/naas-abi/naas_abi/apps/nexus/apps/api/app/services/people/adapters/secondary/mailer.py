"""``PeopleMailer`` through the engine's email service: the invitation mail of
``services/invites`` (``invitation_email.py``) and its notice to someone who was
added (``mail.send_added_notice``)."""

from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.mailer import (
    EngineInvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.mail import (
    resolve_email_service,
    send_added_notice,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    InvitationMail,
    InvitationMailer,
    ProviderChoice,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    PeopleMailer,
    Placement,
    ProviderInfo,
)
from naas_abi_core.services.email.EmailService import EmailService

SignInUrl = Callable[[str, str], str]


class EnginePeopleMailer(PeopleMailer):
    def __init__(
        self,
        *,
        sign_in_url: SignInUrl,
        invitations: InvitationMailer | None = None,
        email: Callable[[], EmailService | None] = resolve_email_service,
    ) -> None:
        """``email``: the engine's email service both mails go through."""
        self._sign_in_url = sign_in_url
        self._invitations = invitations or EngineInvitationMailer(email)
        self._email = email

    async def invitation(
        self,
        *,
        to_email: str,
        provider: ProviderInfo,
        inviter_name: str | None,
        placement: Placement,
        account_made: bool,
    ) -> bool:
        return await self._invitations.send(
            InvitationMail(
                to_email=to_email,
                provider=ProviderChoice(
                    provider.name, provider.display_name, provider.provisioning
                ),
                inviter_name=inviter_name,
                organization_name=placement.organization_name,
                organization_role=placement.organization_role,
                workspace_name=placement.workspace_name,
                workspace_role=placement.workspace_role,
                sign_in_url=self._sign_in_url(to_email, provider.name),
                managed_in_provider=provider.managed_in_provider,
                account_made=account_made,
            )
        )

    async def added(self, *, to_email: str, inviter_name: str | None, placement: Placement) -> bool:
        service = self._email()
        if service is None:
            return False
        return await send_added_notice(
            to_email,
            email_service=service,
            inviter_name=inviter_name,
            organization_name=placement.organization_name,
            organization_role=placement.organization_role,
            workspace_name=placement.workspace_name,
            workspace_role=placement.workspace_role,
        )
