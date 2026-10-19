"""What the invitation routes answer: plain models, with no service behind them
(the organization and workspace routers answer with them too)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    Invitation,
    InviteOutcome,
)
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisioningError,
)
from pydantic import BaseModel, Field


class ProviderView(BaseModel):
    name: str
    display_name: str
    provisioning: str
    # Its people are made in the provider itself: ABI keeps the invitation (a
    # pending grant) and the provider is where the person gets an account.
    managed_in_provider: bool


class ProvidersView(BaseModel):
    # False: no identity provider is configured, and invitations create the
    # account in Nexus as before.
    enabled: bool
    default_provider: str | None = None
    providers: list[ProviderView] = Field(default_factory=list)


class InvitationView(BaseModel):
    id: str
    email: str
    provider: str
    organization_id: str | None = None
    org_role: str | None = None
    workspace_id: str | None = None
    workspace_role: str | None = None
    invited_by: str | None = None
    status: str
    created_at: datetime | None = None


class InvitationsView(BaseModel):
    invitations: list[InvitationView]


class GroupBindingView(BaseModel):
    provider: str
    group: str
    role: str


class GroupBindingsView(BaseModel):
    providers: list[ProviderView]
    bindings: list[GroupBindingView]
    # The roles that can be bound here.
    roles: list[str]


class GroupBindingInput(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    group: str = Field(min_length=1, max_length=256)
    role: str = Field(pattern=r"^(owner|admin|member|viewer)$")


def view(invitation: Invitation) -> InvitationView:
    return InvitationView(
        id=invitation.id,
        email=invitation.email,
        provider=invitation.provider,
        organization_id=invitation.organization_id,
        org_role=invitation.org_role,
        workspace_id=invitation.workspace_id,
        workspace_role=invitation.workspace_role,
        invited_by=invitation.invited_by,
        status=invitation.status,
        created_at=invitation.created_at,
    )


def invite_result(outcome: InviteOutcome) -> dict[str, Any]:
    """What an invite route answers when the person was invited, not added: the
    UI shows a pending invitation, and says when the provider manages people."""
    return {
        "status": "invited",
        "invitation": view(outcome.invitation).model_dump(mode="json"),
        "provider": ProviderView(
            name=outcome.provider.name,
            display_name=outcome.provider.display_name,
            provisioning=outcome.provider.provisioning,
            managed_in_provider=outcome.provider.managed_in_provider,
        ).model_dump(),
        "user_created": outcome.user_created,
        "sign_in_email_sent": outcome.sign_in_email_sent,
        "renewed": outcome.renewed,
        "provisioning_warning": outcome.warning,
    }


# What an invitation raises when the provider could not make the person: nothing
# was granted (the service took its grants back), and the admin may try again.
PROVIDER_FAILURES = (ProviderUnavailableError, ProvisioningError)


def provider_failure(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail=f"The identity provider could not create the user: {exc}",
    )
