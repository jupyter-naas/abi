"""Mail Nexus sends about invitations: what the dev frontend marks, the engine's
email service, and the notice that someone who already has an account was added.

Nexus sends no sign-in mail: signing in is the identity provider's (the built-in
one mails its own code). An invitation of someone with no account is mailed by
``adapters/secondary/mailer.py``; this module mails the people who had one.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from html import escape
from urllib.parse import urlencode, urlparse

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.invites.invitation_email import role_words
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.email.EmailService import EmailService
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

DEV_SUBJECT_PREFIX = "[DEV] "


def frontend_hostname(frontend_url: str) -> str:
    """Hostname from a frontend URL, or a bare host if no scheme is given."""
    raw = (frontend_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower()


def is_dev_frontend(
    frontend_url: str | None = None,
    nexus_env: str | None = None,
) -> bool:
    """True when this deployment is a dedicated .dev frontend.

    Triggers: ``NEXUS_ENV=dev``, or a frontend host that contains ``.dev.``
    or ends with ``.dev``. Generic on purpose: no product hostnames here.
    """
    env = nexus_env if nexus_env is not None else settings.nexus_env
    if str(env or "").strip().lower() == "dev":
        return True
    url = settings.frontend_url if frontend_url is None else frontend_url
    host = frontend_hostname(str(url or ""))
    return ".dev." in host or host.endswith(".dev")


def apply_dev_subject_prefix(subject: str) -> str:
    """Prefix ``[DEV] `` on subjects for .dev frontends. Idempotent."""
    if not is_dev_frontend():
        return subject
    if subject.startswith(DEV_SUBJECT_PREFIX):
        return subject
    return f"{DEV_SUBJECT_PREFIX}{subject}"


def resolve_email_service() -> EmailService | None:
    """Best-effort resolve of the engine email service (API or agent process)."""
    try:
        from naas_abi import ABIModule

        return ABIModule.get_instance().engine.services.email
    except Exception:
        return None


def login_url(email: str) -> str:
    """The web app's login, with the address: the page routes it to its provider."""
    return f"{settings.frontend_url.rstrip('/')}/auth/login?{urlencode({'email': email})}"


def render_added(
    *,
    inviter_name: str | None,
    workspace_name: str | None,
    workspace_role: str | None,
    organization_name: str | None,
    organization_role: str | None,
    to_email: str,
) -> tuple[str, str, str]:
    """``(subject, text, html)``: you were added somewhere, and where to sign in."""
    app_name = settings.email_app_name
    who = inviter_name or "An administrator"
    parts: list[str] = []
    if workspace_name:
        parts.append(f"{role_words(workspace_role)} of the workspace {workspace_name}")
    if organization_name:
        parts.append(f"{role_words(organization_role)} of {organization_name}")
    where = " and ".join(parts) or "a member"
    target = workspace_name or organization_name or app_name
    subject = f"You were added to {target} on {app_name}"
    url = login_url(to_email)
    text = f"{who} added you to {app_name} as {where}.\n\nSign in: {url}\n"
    html = (
        f"<p>{escape(who)} added you to <b>{escape(app_name)}</b> as {escape(where)}.</p>"
        f'<p><a href="{escape(url, quote=True)}">Sign in</a></p>'
    )
    return subject, text, html


async def send_added_notice(
    to_email: str,
    *,
    inviter_name: str | None,
    workspace_name: str | None = None,
    workspace_role: str | None = None,
    organization_name: str | None = None,
    organization_role: str | None = None,
    email_service: EmailService | None = None,
) -> bool:
    """Tell someone who already has an account where they were added. True when
    the email service took it."""
    service = email_service if email_service is not None else resolve_email_service()
    if service is None:
        logger.info("Email service unavailable: no notice for %s", to_email)
        return False
    subject, text, html = render_added(
        inviter_name=inviter_name,
        workspace_name=workspace_name,
        workspace_role=workspace_role,
        organization_name=organization_name,
        organization_role=organization_role,
        to_email=to_email,
    )

    def send() -> None:
        # Nexus's own mail, as its account: it is not the inviting person's mail,
        # and belongs to no workspace, whatever workspace the request names.
        with (
            as_service_account("api") as context,
            use_call_context(replace(context, workspace_id=None)),
        ):
            service.send(
                to_email=to_email,
                subject=apply_dev_subject_prefix(subject),
                text_body=text,
                html_body=html,
                from_email=str(settings.email_from_address),
                from_name=settings.email_from_name,
            )

    await run_in_threadpool(send)
    return True
