"""Nexus's invitations (``services/invites``), as the accounts' directory uses them:
the platform's invitations are that service's, with no organization and no role."""

from __future__ import annotations

from collections.abc import Mapping

from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    InvitationsGateway,
    PendingInvitation,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService


class InvitationsAdapter(InvitationsGateway):
    def __init__(self, service: InvitationService) -> None:
        self._service = service

    async def pending(self) -> list[PendingInvitation]:
        # No organization and no workspace named: every pending invitation.
        return [
            PendingInvitation(i.id, i.email.lower(), i.provider, i.created_at)
            for i in await self._service.pending()
        ]

    async def invite(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        by: str,
        inviter_name: str | None,
    ) -> Mapping[str, object]:
        outcome = await self._service.invite(
            email=email,
            name=name,
            provider=provider,
            organization_id=None,
            org_role=None,
            workspace_id=None,
            workspace_role=None,
            invited_by=by,
            inviter_name=inviter_name,
        )
        return {
            "provider": outcome.provider.name,
            "user_created": outcome.user_created,
            "sign_in_email_sent": outcome.sign_in_email_sent,
            "provisioning_skipped": outcome.provisioning_skipped,
            "renewed": outcome.renewed,
            "warning": outcome.warning,
        }

    async def revoke(self, invitation_id: str) -> None:
        await self._service.revoke(invitation_id)
