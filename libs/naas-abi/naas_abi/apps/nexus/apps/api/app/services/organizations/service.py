from __future__ import annotations

from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.services.organizations.port import OrganizationPermissionPort


@dataclass
class OrganizationPermissionError(PermissionError):
    org_id: str
    user_id: str

    def __str__(self) -> str:
        return "organization_access_denied"


class OrganizationService:
    def __init__(self, adapter: OrganizationPermissionPort):
        self.adapter = adapter

    async def get_organization_role(self, user_id: str, org_id: str) -> str | None:
        return await self.adapter.get_organization_role(user_id=user_id, org_id=org_id)

    async def require_organization_access(self, user_id: str, org_id: str) -> str:
        role = await self.get_organization_role(user_id=user_id, org_id=org_id)
        if role is None:
            raise OrganizationPermissionError(org_id=org_id, user_id=user_id)
        return role
