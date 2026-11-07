"""The invitation email: who invited you, where, as what, and where to sign in.

It carries no secret and no code: signing in is the provider's own flow (the
built-in IdP mails its code when the person asks for one), and the roles wait
in IAM for the address the provider verifies.
"""

from __future__ import annotations

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


def render_invitation(mail: InvitationMail, *, app_name: str) -> tuple[str, str, str]:
    """``(subject, text, html)``."""
    who = mail.inviter_name or "An administrator"
    where = _where(mail)
    target = mail.workspace_name or mail.organization_name or app_name
    subject = f"You are invited to {target} on {app_name}"
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
