"""The invitation email: who invited you, where, as what, and where to sign in.

It carries no secret and no code: signing in is the provider's own flow (the
built-in IdP mails its code when the person asks for one), and the roles wait
in IAM for the address the provider verifies.
"""

from __future__ import annotations

from dataclasses import replace
from html import escape

from naas_abi.apps.nexus.apps.api.app.services.invites.port import InvitationMail

ROLE_WORDS = {
    "owner": "an owner",
    "admin": "an admin",
    "member": "a member",
    "viewer": "a viewer",
}


def role_words(role: str | None) -> str:
    return ROLE_WORDS.get(role or "", f"a {role}" if role else "a member")


def _where(mail: InvitationMail) -> str:
    parts: list[str] = []
    if mail.workspace_name:
        parts.append(f"{role_words(mail.workspace_role)} of the workspace {mail.workspace_name}")
    if mail.organization_name:
        parts.append(f"{role_words(mail.organization_role)} of {mail.organization_name}")
    return " and ".join(parts) or "a member"


# What an organization's people chose (their names, the organization's and the
# workspace's) is quoted and cut to this length; the subject carries none of it.
_TENANT_TEXT = 80


def _quoted(value: str | None) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    if len(text) > _TENANT_TEXT:
        text = text[: _TENANT_TEXT - 1] + "…"
    return f"“{text}”"


def render_invitation(mail: InvitationMail, *, app_name: str) -> tuple[str, str, str]:
    """``(subject, text, html)``. The subject names the platform only (the
    deployment's ``app_name``): what an organization's people wrote appears in the
    body, quoted, never as the sender's own words."""
    mail = replace(
        mail,
        inviter_name=_quoted(mail.inviter_name),
        organization_name=_quoted(mail.organization_name),
        workspace_name=_quoted(mail.workspace_name),
    )
    who = mail.inviter_name or "An administrator"
    where = _where(mail)
    subject = f"You are invited to {app_name}"
    if mail.managed_in_provider:
        how = (
            f"Sign in with your {mail.provider.display_name} account using this "
            "address. Your account is managed there, so there is nothing to create."
        )
    else:
        how = (
            f"Sign in with {mail.provider.display_name} using this address: "
            "you will be asked for a sign-in code the first time."
        )
    text = f"{who} invited you to {app_name} as {where}.\n\n{how}\n\nSign in: {mail.sign_in_url}\n"
    html = (
        f"<p>{escape(who)} invited you to <b>{escape(app_name)}</b> as {escape(where)}.</p>"
        f"<p>{escape(how)}</p>"
        f'<p><a href="{escape(mail.sign_in_url, quote=True)}">Sign in</a></p>'
    )
    return subject, text, html
