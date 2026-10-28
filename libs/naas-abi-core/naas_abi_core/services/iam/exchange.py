"""Token exchange (RFC 8693): the one way a narrow credential is made.

A subject that was already verified is exchanged for an engine-signed token with
its own audience, a short life and, optionally, a narrower ``abi_scope``:

| Subject (``subject_token_type``)           | May become                                   |
|--------------------------------------------|----------------------------------------------|
| an IdP ID or access token                  | ``abi:session``                              |
| a signed-in user a first-party vouches for | ``abi:session`` and every delegated audience |
| an ``abi:session`` token                   | every delegated audience, never back         |
| an ``abi:delegated:agent`` token           | itself, renewed by its actor, 8 hours at most|
| a personal key (``abi_pk_``)               | its own audience (``api-key``, ``coding``)   |
| a link grant (``abi_gk_``)                 | its own audience (``app``, ``preview``)      |

Anything else is refused: a delegated token never becomes another delegated
audience, no token becomes a session but an IdP's, and a service account's key
has its own exchange (``IAMService.exchange_key``).

An exchange never adds a permission: the token carries the user, and the user's
policy still decides; the actor of an agent token is a second policy that must
allow too; a scope narrows further.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import jwt

from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
    vouched_by_first_party,
)
from naas_abi_core.engine.nats_auth import (
    AGENT_AUDIENCE,
    API_KEY_AUDIENCE,
    CLOCK_SKEW_SECONDS,
    DELEGATED_AUDIENCES,
    EXCHANGE_AUDIENCES,
    MAX_DELEGATION_SECONDS,
    SESSION_AUDIENCE,
    InvalidServiceTokenError,
    IssuedToken,
    TokenClaims,
)
from naas_abi_core.services.iam import modules
from naas_abi_core.services.iam.IAMPorts import (
    SUBJECT_TOKEN_TYPES,
    TOKEN_TYPE_ACCESS_TOKEN,
    TOKEN_TYPE_API_KEY,
    TOKEN_TYPE_ID_TOKEN,
    TOKEN_TYPE_JWT,
    TOKEN_TYPE_SESSION,
    IAMNotFoundError,
    KeyRecord,
    KeyRefusedError,
    PermissionDeniedError,
    PrincipalRecord,
    TokenExchange,
)
from naas_abi_core.services.iam.names import parse_resource_name, resource_name
from naas_abi_core.services.iam.tokens import normalize_scope

if TYPE_CHECKING:
    from naas_abi_core.services.iam.IAMService import IAMService

ACTION = "iam:ExchangeToken"
# A principal id as a call names it: a ULID id, or a Nexus user id (a UUID).
_MAX_PRINCIPAL_ID = 256
_DISCOVERY_MODULE_TYPES = ("module", "agent", "app", "model", "job")


# The audience a requester is checked on before a key is looked at, when the
# key's own audience is the one asked for: only one that may exchange for any.
ANY_AUDIENCE = "*"


def audience_resource(audience: str) -> str:
    """What ``iam:ExchangeToken`` is checked on, for ``audience``."""
    return resource_name("iam", "audience", audience)


@dataclass(frozen=True)
class _Subject:
    """A verified subject: who the token will name and what it may become."""

    user_id: str
    allowed: frozenset[str]
    groups: tuple[str, ...] = ()
    scope: tuple[dict[str, Any], ...] | None = None
    session: str | None = None
    since: int | None = None
    resource: str | None = None
    # An agent token being renewed: its actor, claims and requester rule.
    renewing: TokenClaims | None = None
    # The key that was presented; its scope is final.
    key: KeyRecord | None = None


class TokenExchanger:
    def __init__(self, iam: IAMService) -> None:
        self._iam = iam

    # -- the exchange -----------------------------------------------------------

    def exchange(self, request: TokenExchange) -> IssuedToken:
        iam = self._iam
        audience = request.audience
        # A key may be exchanged without naming an audience: the token is the
        # one of its own, read from the key (a caller that cannot tell an API
        # key from a coding key authenticates it once, not once per guess).
        of_the_key = not audience and request.subject_token_type == TOKEN_TYPE_API_KEY
        if not of_the_key and audience not in EXCHANGE_AUDIENCES:
            raise ValueError(f"No tokens for audience {audience!r}")
        handler = {
            TOKEN_TYPE_SESSION: self._vouched,
            TOKEN_TYPE_JWT: self._engine_token,
            TOKEN_TYPE_ID_TOKEN: self._idp_token,
            TOKEN_TYPE_ACCESS_TOKEN: self._idp_token,
            TOKEN_TYPE_API_KEY: self._key,
        }.get(request.subject_token_type)
        if handler is None:
            raise ValueError(
                f"Unknown subject_token_type {request.subject_token_type!r}: "
                f"one of {', '.join(SUBJECT_TOKEN_TYPES)}"
            )
        requested = normalize_scope(request.scope)
        ctx = current_call_context()
        if request.subject_token_type != TOKEN_TYPE_JWT:
            # Before the subject is looked at: a requester that may not exchange
            # must not make IAM ask an identity provider about a token (which
            # would record its user), nor touch a key.
            self._authorize(ctx, None, audience or ANY_AUDIENCE)
        subject = handler(ctx, request, audience)
        if of_the_key:
            (audience,) = subject.allowed
            self._authorize(ctx, subject, audience)
        if audience not in subject.allowed:
            raise PermissionDeniedError(
                ACTION,
                audience_resource(audience),
                message=self._refusal(subject, audience),
            )
        if request.subject_token_type == TOKEN_TYPE_JWT:
            self._authorize(ctx, subject, audience)
        scope = self._narrow(subject, requested)
        actor, actor_name = self._actor(ctx, subject, audience, request.resource)
        # What a key is bound to is the key's own, never the request's.
        resource = (
            subject.resource
            if subject.key is not None
            else subject.resource or request.resource
        )
        now = iam.tokens.now()
        since = subject.since if subject.since is not None else int(now.timestamp())
        not_after = None
        if subject.renewing is not None:
            not_after = since + MAX_DELEGATION_SECONDS
            if int(now.timestamp()) >= not_after:
                raise PermissionDeniedError(
                    ACTION,
                    audience_resource(audience),
                    message="this delegation can no longer be renewed",
                )
        return iam.tokens.issue(
            subject.user_id,
            kind="user",
            audience=audience,
            ttl_seconds=request.ttl_seconds,
            not_after=not_after,
            actor=actor,
            actor_name=actor_name,
            groups=subject.groups,
            scope=scope,
            session=subject.session,
            since=since,
            resource=resource,
            min_issued_at=iam.issue_after_floor(subject.user_id, actor),
        )

    # -- who may exchange -------------------------------------------------------

    def _authorize(
        self, ctx: CallContext, subject: _Subject | None, audience: str
    ) -> None:
        """The requester (the caller, not the user it acts for) needs
        ``iam:ExchangeToken`` on the audience. A module renewing its own
        delegation needs nothing: it only keeps what it was given."""
        renewing = subject.renewing if subject is not None else None
        if renewing is not None and ctx.principal.id == renewing.actor:
            return
        requester = replace(ctx, on_behalf_of=None)
        resource = audience_resource(audience)
        if not self._iam.authorizer.check(requester, ACTION, resource).allowed:
            raise PermissionDeniedError(ACTION, resource)

    @staticmethod
    def _refusal(subject: _Subject, audience: str) -> str:
        if audience == SESSION_AUDIENCE:
            return "only an identity provider's token becomes a session"
        return f"this subject cannot be exchanged for {audience}"

    # -- subjects ---------------------------------------------------------------

    def _vouched(self, ctx: CallContext, request: TokenExchange, _: str) -> _Subject:
        """A user a first-party service (Nexus) verified: the subject token is
        the user's principal id, the groups and session what it saw."""
        if not vouched_by_first_party(ctx):
            raise PermissionDeniedError(
                ACTION,
                message="only a first-party service vouches for a signed-in user",
            )
        user_id = request.subject_token
        if (
            not user_id
            or len(user_id) > _MAX_PRINCIPAL_ID
            or user_id != user_id.strip()
            or any(ord(c) < 33 for c in user_id)
        ):
            raise ValueError("subject_token: a user is named by one plain principal id")
        self._require_active_user(user_id)
        session = request.session_id or None
        if session is not None and len(session) > _MAX_PRINCIPAL_ID:
            raise ValueError("session_id is too long")
        return _Subject(
            user_id=user_id,
            allowed=frozenset(EXCHANGE_AUDIENCES),
            groups=self._groups(request.groups),
            session=session,
        )

    def _engine_token(
        self, ctx: CallContext, request: TokenExchange, audience: str
    ) -> _Subject:
        token = request.subject_token
        try:
            # As of its own issue time: an agent token that expired while its
            # run was quiet is renewed all the same, until the cap.
            at = float(jwt.decode(token, options={"verify_signature": False})["iat"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise InvalidServiceTokenError("not an engine token") from exc
        claims = self._iam.exchange_verifier.verify(token, at=at)
        if claims.audience != AGENT_AUDIENCE and (
            time.time() > claims.expires_at + CLOCK_SKEW_SECONDS
        ):
            raise InvalidServiceTokenError("token has expired")
        if claims.kind != "user":
            raise InvalidServiceTokenError("only a user's token is exchanged")
        self._require_active_user(claims.subject)
        if claims.audience == SESSION_AUDIENCE:
            allowed = frozenset(DELEGATED_AUDIENCES)
            renewing = None
        elif claims.audience == AGENT_AUDIENCE and claims.actor:
            allowed = frozenset({AGENT_AUDIENCE})
            renewing = claims
        else:
            allowed, renewing = frozenset(), None
        return _Subject(
            user_id=claims.subject,
            allowed=allowed,
            groups=self._groups(claims.groups),
            scope=tuple(dict(s) for s in claims.scope)
            if claims.scope is not None
            else None,
            session=claims.session,
            since=claims.since if claims.since is not None else claims.issued_at,
            resource=claims.resource,
            renewing=renewing,
        )

    def _idp_token(
        self, ctx: CallContext, request: TokenExchange, audience: str
    ) -> _Subject:
        authenticator = self._iam.identity_authenticator
        if authenticator is None:
            raise ValueError("No identity provider is configured")
        principal_id, groups = authenticator.authenticate_token(
            request.subject_token, request.subject_token_type
        )
        self._require_active_user(principal_id, known=True)
        return _Subject(
            user_id=principal_id,
            allowed=frozenset({SESSION_AUDIENCE}),
            groups=self._groups(groups),
        )

    def _key(self, ctx: CallContext, request: TokenExchange, audience: str) -> _Subject:
        record, owner = self._iam.authenticate_user_key(request.subject_token)
        target = record.audience or API_KEY_AUDIENCE
        if audience and audience != target:
            raise KeyRefusedError()
        if request.scope is not None:
            raise ValueError("scope: a key's own narrowing is final")
        return _Subject(
            user_id=self._iam.user_name(owner),
            allowed=frozenset({target}),
            scope=tuple(dict(s) for s in record.scope)
            if record.scope is not None
            else None,
            resource=record.resource,
            key=record,
        )

    # -- what the token says ----------------------------------------------------

    def _require_active_user(self, user_id: str, *, known: bool = False) -> None:
        """A suspended or deleted user gets nothing, with one message. A user
        IAM has no record of is a Nexus user (``known``: the caller says IAM must)."""
        record = self._iam.resolve_user(user_id)
        if record is None:
            if known:
                raise KeyRefusedError()
            return
        if not record.active:
            raise KeyRefusedError()

    def _groups(self, group_ids: Sequence[str]) -> tuple[str, ...]:
        """Only ids of active groups: an id of a user or an account in this
        claim must never lend its policies."""
        return self._iam.active_groups(group_ids)

    @staticmethod
    def _narrow(
        subject: _Subject, requested: tuple[dict[str, Any], ...] | None
    ) -> tuple[dict[str, Any], ...] | None:
        """An exchange only narrows: the subject's own scope is kept, and a
        scope is not narrowed twice (a statement list has no intersection)."""
        if requested is None:
            return subject.scope
        if subject.scope is not None:
            raise ValueError(
                "scope: this credential is already narrowed; it is not narrowed again"
            )
        return requested

    def _actor(
        self,
        ctx: CallContext,
        subject: _Subject,
        audience: str,
        resource: str | None,
    ) -> tuple[str | None, str | None]:
        """The service account an agent token names as ``act`` (its id and
        name): the module that owns ``resource``, else the requester. Never a
        request field."""
        if audience != AGENT_AUDIENCE:
            return None, None
        if subject.renewing is not None:
            return subject.renewing.actor, subject.renewing.actor_name
        if resource:
            account = self._module_account(resource)
            return account.id, account.name
        requester = self._iam.resolve_principal(ctx.principal)
        if requester is None or requester.kind != "service_account":
            raise PermissionDeniedError(
                ACTION, message="an agent token is for a service account"
            )
        return requester.id, requester.name

    def _module_account(self, resource: str) -> PrincipalRecord:
        """The account of the module a resource names: a discovery module,
        agent, app, model or job of it, or the module's own account
        (``abi:-:-:iam:principal/<sa id>``), which is how a caller that only
        knows the host it is calling (its ``<sa>``) names it."""
        try:
            parsed = parse_resource_name(resource)
        except ValueError as exc:
            raise ValueError(f"resource: {exc}") from exc
        parts = parsed.segments
        if parsed.service == "iam" and parsed.type == "principal" and len(parts) == 1:
            try:
                found = self._iam.store.get_principal(parts[0])
            except IAMNotFoundError:
                raise KeyRefusedError() from None
            if (
                found.kind != "service_account"
                or not found.active
                or modules.parse_account(found.name) is None
            ):
                raise KeyRefusedError()
            return found
        if (
            parsed.service != "discovery"
            or parsed.type not in _DISCOVERY_MODULE_TYPES
            or len(parts) < 2
        ):
            raise ValueError(
                "resource: an agent token is for a discovery module, agent, app, "
                "model or job"
            )
        record = self._iam.store.find_service_account(
            modules.account_name(parts[0], parts[1])
        )
        if record is None or not record.active:
            raise KeyRefusedError()
        return record
