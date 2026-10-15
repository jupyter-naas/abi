"""Ports of Nexus's sign-in through the engine's identity providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from naas_abi_core.services.identity.IdentityPorts import ProviderInfo, SignIn


@dataclass(frozen=True)
class LoginRequest:
    """A sign-in in flight. ``state_hash`` and ``binding_hash`` are SHA-256 hex."""

    state_hash: str
    provider: str
    nonce: str
    code_verifier: str = field(repr=False)
    binding_hash: str = field(repr=False)
    next_path: str
    expires_at: datetime


@dataclass(frozen=True)
class SessionRecord:
    """A browser session. The provider's tokens are stored encrypted."""

    id: str
    user_id: str
    principal_id: str
    provider: str
    group_ids: tuple[str, ...]
    refresh_token_enc: str | None = field(repr=False)
    id_token_enc: str | None = field(repr=False)
    refresh_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class OidcUser:
    id: str
    email: str
    name: str
    principal_id: str | None
    idp_issuer: str | None
    idp_subject: str | None


class OidcSessionPersistencePort(ABC):
    """Nexus's tables for sign-in: login requests, sessions and users."""

    @abstractmethod
    async def save_login_request(self, request: LoginRequest) -> None: ...

    @abstractmethod
    async def take_login_request(self, state_hash: str) -> LoginRequest | None:
        """The request, deleted in the same step: a state is used once."""

    @abstractmethod
    async def purge_login_requests(self, now: datetime) -> None:
        """Drop the expired ones."""

    @abstractmethod
    async def user_by_principal(self, principal_id: str) -> OidcUser | None: ...

    @abstractmethod
    async def email_taken(self, email: str, *, except_user_id: str | None = None) -> bool: ...

    @abstractmethod
    async def create_user(
        self,
        *,
        user_id: str,
        email: str,
        name: str,
        principal_id: str,
        provider: str,
        issuer: str,
        subject: str,
        now: datetime,
    ) -> OidcUser:
        """A user signed in through a provider: no password, no workspace."""

    @abstractmethod
    async def update_user(
        self, user_id: str, *, email: str | None, name: str | None, now: datetime
    ) -> None:
        """Refresh the profile a provider states; ``None`` keeps a field."""

    @abstractmethod
    async def provider_for_domain(self, domain: str) -> str | None:
        """The provider a verified organization domain routes to, if any."""

    @abstractmethod
    async def create_session(self, session: SessionRecord, *, user_agent: str | None) -> None: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> SessionRecord | None: ...

    @abstractmethod
    async def update_session(
        self,
        session_id: str,
        *,
        group_ids: tuple[str, ...] | None = None,
        refresh_token_enc: str | None = None,
        id_token_enc: str | None = None,
        refresh_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> None: ...

    @abstractmethod
    async def revoke_session(self, session_id: str, now: datetime) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...


class IdentityGateway(ABC):
    """The engine's identity service, as Nexus (``api``) calls it."""

    @abstractmethod
    async def providers(self) -> tuple[list[ProviderInfo], str | None]:
        """The configured providers and the default one."""

    @abstractmethod
    async def authorization_url(
        self,
        provider: str,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_challenge: str,
        login_hint: str | None,
    ) -> str: ...

    @abstractmethod
    async def exchange_code(
        self,
        provider: str,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        nonce: str,
    ) -> SignIn: ...

    @abstractmethod
    async def refresh(self, provider: str, *, refresh_token: str, principal_id: str) -> SignIn: ...

    @abstractmethod
    async def revoke(self, provider: str, *, refresh_token: str) -> bool: ...

    @abstractmethod
    async def end_session_url(
        self,
        provider: str,
        *,
        id_token_hint: str | None,
        post_logout_redirect_uri: str | None,
    ) -> str | None: ...


class PrincipalGateway(ABC):
    """What Nexus asks IAM about the users it signs in."""

    @abstractmethod
    async def is_active(self, principal_id: str) -> bool:
        """Not suspended or deleted: suspension takes effect at once."""

    @abstractmethod
    async def admit(self, principal_id: str) -> None:
        """TRANSITIONAL (#65): attach ``builtin.transitional.nexus_user``, so
        Nexus still decides what the user may do, as for its own users."""
