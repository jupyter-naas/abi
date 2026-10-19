"""Who is calling: the caller identity of the call being served.

See docs/specs/rfcs/20261013_identity-and-authorization.md, §10. The variable
lives here, in the core-free SDK, and ``naas_abi_core.engine.call_context``
re-exports it: an engine and the SDK clients it runs read the same value. A
core installed without the SDK (no ``nats`` extra) runs a verbatim copy of
this file, ``naas_abi_core/engine/call_context_types.py``; keep them equal.

Primary adapters set it, and only from verified credentials (a NATS request's
``Nats-Auth-Token``, a Nexus session). Never from request-body fields:
``CallContext.principal_id`` and ``tenant_id`` in the proto are reserved and
ignored. Code called in process inherits its caller's context. ``asyncio``
tasks and ``asyncio.to_thread`` copy it; raw threads and executor submissions
need ``contextvars.copy_context().run``.

The user a call acts for travels in a delegated token (``abi:delegated:agent``,
RFC §9.4) that names the user and the service acting for them, never in a
header: core's RPC client and the SDK ``Transport`` of ``api`` and ``engine``
send one for the call's user (``CallContext.user``); a module host runs the
calls of an invocation with the delegation it was handed
(``CallContext.delegated_token``).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Literal

PrincipalKind = Literal["user", "service_account", "anonymous"]
# A narrowing statement from a token's ``abi_scope``. IAM owns its schema.
Statement = Mapping[str, Any]


@dataclass(frozen=True)
class Principal:
    """Who acts: a user, a service account, or nobody."""

    # usr_/grp_/sa_ ids once IAM assigns them. Until then a service account's
    # id is its name ("api", "engine", a module) and a user's is the id its
    # caller vouches for (a Nexus user id).
    id: str
    kind: PrincipalKind
    name: str | None = None  # a service account's name, e.g. "api"
    issuer: str | None = None  # users: the IdP issuer
    subject: str | None = None  # users: the IdP subject
    groups: frozenset[str] = frozenset()


def service_account(name: str) -> Principal:
    """The service account named ``name``."""
    if not name:
        raise ValueError("A service account needs a name")
    return Principal(id=name, kind="service_account", name=name)


def user(principal_id: str) -> Principal:
    """The user whose principal id is ``principal_id``."""
    if not principal_id:
        raise ValueError("A user needs a principal id")
    return Principal(id=principal_id, kind="user")


ANONYMOUS_PRINCIPAL = Principal(id="anonymous", kind="anonymous")


@dataclass(frozen=True)
class CallContext:
    """The call being served: who acts, for whom, and what it targets."""

    principal: Principal  # the actor: who holds the credential
    on_behalf_of: Principal | None = None  # the user, when acting for one
    audience: str | None = None
    token_id: str | None = None  # the token's jti, for audit
    # When the token was issued (its iat): IAM refuses a token issued before
    # its principal's tokens were revoked.
    token_issued_at: int | None = None
    scope: tuple[Statement, ...] | None = None  # abi_scope narrowing
    # The target workspace of a create: a request input, not identity.
    workspace_id: str | None = None
    trace_id: str | None = None
    # How the work started ("api", "cli", "configuration", ...), stamped on events.
    triggered_via: str | None = None
    # The delegation a module host runs an invocation with: an
    # ``abi:delegated:agent`` token naming the module and the user, sent in
    # place of the module's own token on the kernel calls the run makes for that
    # user. A credential: never compared, never printed.
    delegated_token: str | None = field(default=None, compare=False, repr=False)

    @property
    def user(self) -> Principal | None:
        """The call's user: whom the call acts for, else the actor if it is a user."""
        if self.on_behalf_of is not None:
            return self.on_behalf_of
        return self.principal if self.principal.kind == "user" else None


# What a call carries when no primary adapter has set anything.
ANONYMOUS = CallContext(principal=ANONYMOUS_PRINCIPAL)

_call_context: ContextVar[CallContext] = ContextVar(
    "abi_call_context", default=ANONYMOUS
)


def current_call_context() -> CallContext:
    """The context of the call being served; ``ANONYMOUS`` outside any call."""
    return _call_context.get()


@contextmanager
def use_call_context(context: CallContext) -> Iterator[CallContext]:
    """Serve the block as ``context``; the previous context comes back on exit."""
    token = _call_context.set(context)
    try:
        yield context
    finally:
        _call_context.reset(token)


def set_call_context(context: CallContext) -> Token[CallContext]:
    """Replace the current context until ``reset_call_context(token)``.

    For code that cannot wrap a block (a ContextVar-style API, a context
    being prepared for a worker); everything else uses ``use_call_context``.
    """
    return _call_context.set(context)


def reset_call_context(token: Token[CallContext]) -> None:
    _call_context.reset(token)
