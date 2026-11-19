"""``PeopleMailer`` through the engine's email service: the invitation mail of
``services/invites`` (``invitation_email.py``) and its notice to someone who was
added (``mail.send_added_notice``)."""

from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.mailer import (
    EngineInvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.mail import send_added_notice
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

SignInUrl = Callable[[str, str], str]


class EnginePeopleMailer(PeopleMailer):
    def __init__(
        self,
        *,
        sign_in_url: SignInUrl,
        invitations: InvitationMailer | None = None,
    ) -> None:
        self._sign_in_url = sign_in_url
        self._invitations = invitations or EngineInvitationMailer()

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
        return await send_added_notice(
            to_email,
            inviter_name=inviter_name,
            organization_name=placement.organization_name,
            organization_role=placement.organization_role,
            workspace_name=placement.workspace_name,
            workspace_role=placement.workspace_role,
        )
