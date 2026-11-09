"""Personal API keys, kept by IAM.

A personal API key is ``abi_pk_<id>_<secret>``: a credential of its owner for
scripts and tools. IAM stores only a hash of the secret, so the key is shown
once, when it is made. It

* expires (a year at most, a year by default) and can be revoked at any time:
  it stops at the next request;
* may be narrowed to a subset of what its owner may do (a scope, the token's
  ``abi_scope``): *read only*, or statements of the owner's own writing. A key
  can never do more than its owner's policies allow, and the owner's side
  decides as well;
* is exchanged for the audience ``abi:delegated:api-key``, which every route
  but the account and the keys' own management takes (``credentials.py``).

This service is Nexus's side of the management API: it makes, lists and revokes
the keys of the signed-in user, as ``api`` on their behalf, so IAM's own rules
(``iam:CreateKey``, ``iam:ListKeys``, ``iam:RevokeKey`` on their own keys)
decide. Nothing here keeps a key.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_auth import API_KEY_AUDIENCE, IssuedToken
from naas_abi_core.services.iam.IAMPorts import (
    TOKEN_TYPE_API_KEY,
    KeyRecord,
    TokenExchange,
)

Access = Literal["full", "read", "custom"]
Status = Literal["active", "revoked", "expired"]
MAX_DAYS = 365
# A statement lists at most this many patterns (IAM's limit for a scope).
_PATTERNS = 64


class ApiKeysUnavailable(RuntimeError):
    """IAM is not there to keep keys (a process without the engine)."""


@dataclass(frozen=True)
class ApiKey:
    """What the owner may know of a key: never its secret."""

    id: str
    name: str
    prefix: str
    created_at: datetime | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    status: Status
    access: Access
    scope: tuple[dict[str, Any], ...] | None


@dataclass(frozen=True)
class CreatedApiKey:
    key: ApiKey
    secret: str


class ApiKeyService:
    def __init__(self, iam: Callable[[], Any | None] | None = None) -> None:
        self._iam = iam

    def _engine(self) -> Any:
        iam = (self._iam or credentials.IAM)()
        if iam is None:
            raise ApiKeysUnavailable("API keys need the engine's IAM")
        return iam

    # -- the owner's keys ---------------------------------------------------------

    def list_keys(self, user_id: str) -> list[ApiKey]:
        """The owner's API keys, newest first. Keys made for something else (a
        coding environment, a link) are not API keys and are not listed."""
        iam = self._engine()
        read_only = self._read_only(iam)
        with _acting_for(user_id):
            found = iam.list_keys(user_id)
        keys = [
            _view(key, read_only)
            for key in found
            if key.kind == "personal" and (key.audience or API_KEY_AUDIENCE) == API_KEY_AUDIENCE
        ]
        return sorted(
            keys, key=lambda k: k.created_at or datetime.min.replace(tzinfo=UTC), reverse=True
        )

    def create_key(
        self,
        user_id: str,
        *,
        name: str,
        expires_in_days: int = MAX_DAYS,
        access: Access = "full",
        scope: Sequence[Mapping[str, Any]] | None = None,
    ) -> CreatedApiKey:
        """A new key. ``access``: ``full`` (as the owner), ``read`` (only what
        reads and lists) or ``custom`` (``scope``: Allow statements).
        ``ValueError`` for an invalid request; ``IAMConflictError`` at five
        active keys."""
        if not 1 <= expires_in_days <= MAX_DAYS:
            raise ValueError(f"A key lasts 1 to {MAX_DAYS} days")
        name = name.strip()
        if not name:
            raise ValueError("A key needs a name")
        iam = self._engine()
        narrowing = self._scope_of(iam, access, scope)
        with _acting_for(user_id):
            created = iam.create_key(
                user_id,
                description=name,
                scope=narrowing,
                expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
            )
        return CreatedApiKey(_view(created.record, self._read_only(iam)), created.value)

    def revoke_key(self, user_id: str, key_id: str) -> ApiKey:
        """Revoke one of the owner's keys; it stops at the next request.
        ``IAMNotFoundError`` for a key that is not theirs."""
        iam = self._engine()
        with _acting_for(user_id):
            record = iam.revoke_key(user_id, key_id)
        return _view(record, self._read_only(iam))

    # -- the exchange (scripts) ------------------------------------------------------

    def exchange(self, client_secret: str) -> IssuedToken:
        """The token a personal key buys (``abi:delegated:api-key``, ten minutes
        at most), for a script that wants a short-lived credential. As ``api``,
        the one account that exchanges for any audience. ``KeyRefusedError``,
        one message, for every refusal."""
        iam = self._engine()
        with as_service_account("api"):
            return iam.exchange_token(
                TokenExchange(
                    subject_token=client_secret,
                    subject_token_type=TOKEN_TYPE_API_KEY,
                    audience=API_KEY_AUDIENCE,
                )
            )

    # -- scopes -----------------------------------------------------------------------

    def _scope_of(
        self, iam: Any, access: Access, scope: Sequence[Mapping[str, Any]] | None
    ) -> tuple[dict[str, Any], ...] | None:
        if access == "full":
            if scope is not None:
                raise ValueError("A key with full access has no scope")
            return None
        if access == "read":
            if scope is not None:
                raise ValueError("A read-only key has no scope of its own")
            return self._read_only(iam)
        if access == "custom":
            if not scope:
                raise ValueError("A custom key names its statements")
            return tuple(dict(s) for s in scope)
        raise ValueError(f"Unknown access {access!r}")

    @staticmethod
    def _read_only(iam: Any) -> tuple[dict[str, Any], ...]:
        """Allow every registered action that reads or lists, on anything: the
        owner's own policies still decide what they may read."""
        names: list[str] = []
        for catalog in iam.list_catalogs():
            for action in catalog.actions:
                if action.level in ("read", "list"):
                    names.append(catalog.qualified(action.name))
        names.sort()
        return tuple(
            {"effect": "Allow", "actions": names[i : i + _PATTERNS], "resources": ["*"]}
            for i in range(0, len(names), _PATTERNS)
        )


def _acting_for(user_id: str):
    return use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user(user_id))
    )


def _view(record: KeyRecord, read_only: tuple[dict[str, Any], ...]) -> ApiKey:
    now = datetime.now(UTC)
    status: Status = "active"
    if record.revoked_at is not None:
        status = "revoked"
    elif record.expires_at is not None and record.expires_at <= now:
        status = "expired"
    scope = tuple(dict(s) for s in record.scope) if record.scope is not None else None
    access: Access = "full"
    if scope is not None:
        same = json.dumps(scope, sort_keys=True) == json.dumps(read_only, sort_keys=True)
        access = "read" if same else "custom"
    return ApiKey(
        id=record.key_id,
        name=record.description,
        prefix=f"abi_pk_{record.key_id}",
        created_at=record.created_at,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
        status=status,
        access=access,
        scope=scope,
    )
