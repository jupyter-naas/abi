"""The provider's records. Each is one document in the module's namespace."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from authlib.oauth2.rfc6749 import ClientMixin, TokenMixin
from authlib.oidc.core import AuthorizationCodeMixin

from naas_abi_idp.ports import CollectionSpec

USERS = "users"
GROUPS = "groups"
CLIENTS = "clients"
CHALLENGES = "challenges"
AUTH_REQUESTS = "auth_requests"
CODES = "codes"
SESSIONS = "sessions"
REFRESH_TOKENS = "refresh_tokens"
RATE_LIMITS = "rate_limits"
KEYS = "keys"

COLLECTIONS = (
    CollectionSpec(USERS, unique=(("email",),), indexed=("email",)),
    CollectionSpec(GROUPS, unique=(("name",),), indexed=("name",)),
    CollectionSpec(CLIENTS),
    CollectionSpec(CHALLENGES),
    CollectionSpec(AUTH_REQUESTS),
    CollectionSpec(CODES),
    CollectionSpec(SESSIONS, indexed=("user_id",)),
    CollectionSpec(REFRESH_TOKENS, indexed=("family", "user_id", "code_id")),
    CollectionSpec(RATE_LIMITS),
    CollectionSpec(KEYS),
)


@dataclass
class User:
    """A person who signs in. ``id`` is the ``sub`` of their tokens: it never
    changes, whatever happens to the email."""

    id: str
    email: str
    name: str
    created_at: float
    disabled: bool = False
    # Ids of the groups the user belongs to; the groups claim lists their names.
    groups: list[str] = field(default_factory=list)
    password_hash: str | None = field(default=None, repr=False)
    last_login_at: float | None = None

    def to_doc(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> User:
        return cls(**data)

    def public(self) -> dict[str, Any]:
        """What the admin API shows: never the password hash."""
        data = asdict(self)
        data.pop("password_hash")
        data["has_password"] = self.password_hash is not None
        return data


@dataclass
class Group:
    id: str
    name: str
    created_at: float
    description: str = ""

    def to_doc(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> Group:
        return cls(**data)


@dataclass
class Client(ClientMixin):
    """A relying party. Authlib reads it through ``ClientMixin``."""

    client_id: str
    name: str
    created_at: float
    redirect_uris: list[str] = field(default_factory=list)
    grant_types: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    secret_hash: str | None = field(default=None, repr=False)
    disabled: bool = False
    # "config" (seeded at start, follows the configuration) or "admin".
    source: str = "admin"

    # -- authlib's ClientMixin ----------------------------------------------

    def get_client_id(self) -> str:
        return self.client_id

    def get_default_redirect_uri(self) -> str | None:
        return self.redirect_uris[0] if self.redirect_uris else None

    def get_allowed_scope(self, scope: str) -> str:
        if not scope:
            return ""
        allowed = set(self.scopes)
        return " ".join(s for s in scope.split() if s in allowed)

    def check_redirect_uri(self, redirect_uri: str) -> bool:
        # Exact match, as OAuth 2.0 Security BCP asks: no prefixes, no wildcards.
        return redirect_uri in self.redirect_uris

    def check_client_secret(self, client_secret: str) -> bool:
        from naas_abi_idp.secrets_hash import verify_secret

        return (
            self.secret_hash is not None
            and verify_secret(client_secret, self.secret_hash)
            and not self.disabled
        )

    def check_endpoint_auth_method(self, method: str, endpoint: str) -> bool:
        # A client with a secret proves it at every endpoint; one without is public.
        if self.secret_hash is None:
            return method == "none"
        return method in ("client_secret_basic", "client_secret_post")

    def check_response_type(self, response_type: str) -> bool:
        return response_type == "code"

    def check_grant_type(self, grant_type: str) -> bool:
        return not self.disabled and grant_type in self.grant_types

    @property
    def id_token_signed_response_alg(self) -> str:
        return "ES256"

    # -- documents ----------------------------------------------------------

    def to_doc(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> Client:
        return cls(**data)

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("secret_hash")
        data["confidential"] = self.secret_hash is not None
        return data


@dataclass
class AuthorizationCode(AuthorizationCodeMixin):
    """An authorization code, kept by its hash until its single use."""

    id: str  # the hash of the code
    client_id: str
    user_id: str
    redirect_uri: str
    scope: str
    expires_at: float
    auth_time: int
    code_challenge: str | None = None
    code_challenge_method: str | None = None
    nonce: str | None = None
    amr: list[str] = field(default_factory=list)
    used: bool = False

    def get_redirect_uri(self) -> str:
        return self.redirect_uri

    def get_scope(self) -> str:
        return self.scope

    def get_nonce(self) -> str | None:
        return self.nonce

    def get_auth_time(self) -> int:
        return self.auth_time

    def get_acr(self) -> str | None:
        return None

    def get_amr(self) -> list[str] | None:
        return self.amr or None

    def is_expired(self, now: float) -> bool:
        return self.expires_at <= now

    def to_doc(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> AuthorizationCode:
        return cls(**data)


@dataclass
class RefreshToken(TokenMixin):
    """A refresh token, kept by its hash. Each use replaces it with a new one in
    the same ``family``; presenting a replaced one revokes the family."""

    id: str  # the hash of the token
    family: str
    client_id: str
    user_id: str
    scope: str
    created_at: float
    expires_at: float
    code_id: str | None = None
    revoked: bool = False
    rotated: bool = False

    def check_client(self, client: Client) -> bool:
        return client.client_id == self.client_id

    def get_scope(self) -> str:
        return self.scope

    def is_revoked(self) -> bool:
        return self.revoked

    def to_doc(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> RefreshToken:
        return cls(**data)
