from __future__ import annotations

from abc import ABC, abstractmethod


class OrganizationPermissionPort(ABC):
    @abstractmethod
    async def get_organization_role(self, user_id: str, org_id: str) -> str | None:
        raise NotImplementedError
