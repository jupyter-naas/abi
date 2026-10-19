"""The caller identity of the call a domain service is serving.

The types and the context variable are ``naas_abi_sdk.call_context``, re-exported
here so the engine and the SDK clients it runs share one variable; a core
installed without the SDK uses ``call_context_types``, a verbatim copy. See
docs/specs/rfcs/20261013_identity-and-authorization.md, §10.

Who sets it:

* NATS primary adapters, from the verified ``Nats-Auth-Token``: a delegated
  token names the user a service acts for (``naas_abi_core.engine.nats_identity``);
* Nexus, per request: ``api`` on behalf of the signed-in user (an unrevoked
  session token), else ``ANONYMOUS``;
* in-process callers inherit their caller's context; work that runs for no
  caller uses ``as_service_account`` (engine-hosted jobs as ``engine``,
  Nexus's configuration seeding as ``api``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

from naas_abi_core import logger

try:
    from naas_abi_sdk import call_context as _definitions
except ModuleNotFoundError:
    # Without the nats extra there is no SDK, and no SDK client to share the
    # variable with: the same definitions, copied verbatim.
    from naas_abi_core.engine import (  # type: ignore[no-redef]
        call_context_types as _definitions,
    )

ANONYMOUS = _definitions.ANONYMOUS
ANONYMOUS_PRINCIPAL = _definitions.ANONYMOUS_PRINCIPAL
CallContext = _definitions.CallContext
Principal = _definitions.Principal
PrincipalKind = _definitions.PrincipalKind
Statement = _definitions.Statement
current_call_context = _definitions.current_call_context
reset_call_context = _definitions.reset_call_context
service_account = _definitions.service_account
set_call_context = _definitions.set_call_context
use_call_context = _definitions.use_call_context
user = _definitions.user


@contextmanager
def as_service_account(name: str) -> Iterator[CallContext]:
    """Run the block as the engine's own service account ``name``, for no user.

    In process only: remote code holds nothing but its token. The trace and
    the target workspace of the surrounding call are kept.
    """
    logger.debug(f"Running as service account {name!r}")
    context = replace(
        current_call_context(),
        principal=service_account(name),
        on_behalf_of=None,
        audience=None,
        token_id=None,
        token_issued_at=None,
        scope=None,
        delegated_token=None,
    )
    with use_call_context(context):
        yield context


# The first-party accounts whose word about their user is trusted (RFC §10.2).
FIRST_PARTY_ACCOUNTS = ("api", "engine")


def call_subject(context: CallContext | None = None) -> str | None:
    """Whom a call concerns: its user (RFC §10.1), else its calling principal;
    None for an anonymous call.

    The one rule for the owner of what a call creates (an agent run, an
    environment), the actor of what it records, and the forge or orchestrator
    account it acts as. Never a request field.
    """
    context = context if context is not None else current_call_context()
    if context.user is not None:
        return context.user.id
    if context.principal.kind == "anonymous":
        return None
    return context.principal.id


def vouched_by_first_party(context: CallContext | None = None) -> bool:
    """Whether the call's actor is a first-party account (``api``, ``engine``)
    that verified what it says about its user, such as the user's email."""
    principal = (context if context is not None else current_call_context()).principal
    return (
        principal.kind == "service_account"
        and (principal.name or principal.id) in FIRST_PARTY_ACCOUNTS
    )
