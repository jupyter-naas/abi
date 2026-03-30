from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["owner", "admin", "member", "viewer"]
ResourceType = Literal["workspace", "conversation", "organization"]


@dataclass(frozen=True)
class AuthorizationSubject:
    user_id: str
    token_scopes: set[str] = field(default_factory=set)
    is_authenticated: bool = True


@dataclass(frozen=True)
class TokenData:
    user_id: str
    scopes: set[str] = field(default_factory=set)
    is_authenticated: bool = True


@dataclass(frozen=True)
class RequestContext:
    token_data: TokenData
    session_id: str | None = None
    is_admin_access: bool = False
    impersonated_user_id: str | None = None

    @property
    def actor_user_id(self) -> str:
        return self.impersonated_user_id or self.token_data.user_id

    @property
    def scopes(self) -> set[str]:
        return self.token_data.scopes

    @property
    def is_authenticated(self) -> bool:
        return self.token_data.is_authenticated


@dataclass(frozen=True)
class AuthorizationRequest:
    subject: AuthorizationSubject
    action: str
    resource_type: ResourceType
    resource_id: str
    required_scope: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    required_role: str | None = None
    required_scope: str | None = None


@dataclass(frozen=True)
class ConversationAccessRecord:
    conversation_id: str
    workspace_id: str
    owner_user_id: str


class IAMPolicyPort(ABC):
    @abstractmethod
    async def get_workspace_role(self, user_id: str, workspace_id: str) -> Role | None:
        pass

    @abstractmethod
    async def get_organization_role(self, user_id: str, org_id: str) -> Role | None:
        pass

    @abstractmethod
    async def get_conversation_access_record(
        self, conversation_id: str
    ) -> ConversationAccessRecord | None:
        pass
