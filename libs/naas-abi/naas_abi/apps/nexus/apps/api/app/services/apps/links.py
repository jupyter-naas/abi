"""Links to an app: grants IAM stores, revocable, at most eight hours (RFC §9.3).

A link sits in a URL or a cookie, where the page's own JavaScript can read it.
It is never a session, and no secret of Nexus signs it: it is a *grant* of the
user who opened it (``abi_gk_<id>_<secret>``), made by IAM for one audience,

* ``abi:delegated:app``: an ``/app-html/`` link and an ``/app-remote/`` grant,
* ``abi:delegated:preview``: an ``/app-preview/`` link,

bound to what it opens (``resource``) and narrowed to what opening it needs
(``scope``, the token's ``abi_scope``). IAM stores only a hash of it, so it can
be revoked (``iam.revoke_key``), ends with its owner (suspension, and
``revoke_tokens``), and never outlives eight hours. Each request that presents
one asks IAM again: opening a link is exchanging its grant, so revocation takes
effect at the next request.

Nexus reads the grant's facts straight from IAM in process
(``authenticate_user_key``): the exchange without a token nobody would send
anywhere, which says the same things (the user, the resource, the scope).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi_core.engine.call_context import (
    CallContext,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_auth import APP_AUDIENCE, PREVIEW_AUDIENCE
from naas_abi_core.services.iam.IAMPorts import IAMConflictError, KeyRefusedError

# IAM's limit for a grant: a link is reopened to renew, never kept.
MAX_MINUTES = 8 * 60

# What each kind of link is bound to (``resource``).
APP_HTML_ROOT = "/app-html/"  # an /app-html/ link: a path prefix below it
PREVIEW = "preview"  # preview/<workspace id>/<slug>
REMOTE_APP = "app-remote"  # app-remote/<module id>/<app>


class LinksUnavailable(RuntimeError):
    """IAM is not there to make or read a link (an engine-less process)."""


class LinkLimitReached(RuntimeError):
    """The user holds as many live links as IAM allows: some must end first."""


@dataclass(frozen=True)
class OpenedLink:
    user_id: str
    resource: str
    scope: tuple[dict[str, Any], ...] | None
    expires_at: datetime | None


def preview_resource(workspace_id: str, slug: str) -> str:
    return f"{PREVIEW}/{workspace_id}/{slug}"


def remote_app_resource(module_id: str, app: str) -> str:
    return f"{REMOTE_APP}/{module_id}/{app}"


def remote_app_scope(module_id: str, app: str) -> tuple[dict[str, Any], ...]:
    """What opening a remote app asks of the kernel: ``discovery:OpenApp`` on
    that app, in any discovery project, and nothing else."""
    from naas_abi_core.services.iam.names import encode_segment

    return (
        {
            "effect": "Allow",
            "actions": ["discovery:OpenApp"],
            "resources": [
                f"abi:-:-:discovery:app/*/{encode_segment(module_id)}/{encode_segment(app)}"
            ],
        },
    )


def _iam() -> Any:
    iam = credentials.IAM()
    if iam is None:
        raise LinksUnavailable("A link needs the engine's IAM")
    return iam


def mint_link(
    *,
    user_id: str,
    audience: str,
    resource: str,
    scope: tuple[dict[str, Any], ...] = (),
    minutes: int,
    not_after: datetime | None = None,
    description: str = "",
) -> tuple[str, int]:
    """``(grant, seconds it lasts)`` of a link for ``user_id``, never longer than
    eight hours, nor than ``not_after`` (the credential it is opened from: a
    share link stays a share link). Made as ``api`` for the user, who needs
    ``iam:CreateKey`` on their own keys (every user holds it)."""
    if audience not in (APP_AUDIENCE, PREVIEW_AUDIENCE):
        raise ValueError("A link is for an app or a preview")
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=max(1, min(minutes, MAX_MINUTES)))
    if not_after is not None:
        expires_at = min(expires_at, not_after)
    if expires_at <= now + timedelta(seconds=1):
        raise ValueError("The credential this link would open from has expired")
    iam = _iam()
    try:
        with use_call_context(
            CallContext(principal=service_account("api"), on_behalf_of=user(user_id))
        ):
            created = iam.create_key(
                user_id,
                description=description or f"link: {resource}"[:200],
                kind="grant",
                audience=audience,
                resource=resource,
                scope=scope,
                expires_at=expires_at,
            )
    except IAMConflictError as exc:
        raise LinkLimitReached(
            "Too many links are open for this account: wait for some to expire"
        ) from exc
    return created.value, int((expires_at - now).total_seconds())


def open_link(value: str, audience: str) -> OpenedLink | None:
    """What a link says, or None for anything IAM refuses: unknown, wrong,
    revoked, expired, of another audience, of a suspended or deleted user."""
    if not value:
        return None
    iam = credentials.IAM()
    authenticate = getattr(iam, "authenticate_user_key", None)
    if authenticate is None:
        return None
    try:
        record, owner = authenticate(value)
    except KeyRefusedError:
        return None
    if record.kind != "grant" or record.audience != audience or not record.resource:
        return None
    return OpenedLink(
        user_id=iam.user_name(owner),
        resource=record.resource,
        scope=tuple(dict(s) for s in record.scope) if record.scope is not None else None,
        expires_at=record.expires_at,
    )


async def amint_link(**fields: Any) -> tuple[str, int]:
    return await asyncio.to_thread(mint_link, **fields)


async def aopen_link(value: str, audience: str) -> OpenedLink | None:
    return await asyncio.to_thread(open_link, value, audience)
