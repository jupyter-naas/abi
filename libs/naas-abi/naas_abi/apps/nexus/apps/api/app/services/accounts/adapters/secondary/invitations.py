"""Nexus's pending invitations (``services/invites``), as the accounts' directory
lists and withdraws them: those made before an invitation made the account."""

from __future__ import annotations

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

    async def revoke(self, invitation_id: str) -> None:
        await self._service.revoke(invitation_id)
