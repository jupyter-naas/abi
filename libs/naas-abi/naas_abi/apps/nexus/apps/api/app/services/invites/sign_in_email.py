"""Shared invite sign-in email (magic link + OTP) for org/workspace invites."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService, MagicLinkChallenge
from naas_abi_core.services.email.EmailService import EmailService

logger = logging.getLogger(__name__)


class _SafeTemplateValues(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def resolve_email_service() -> EmailService | None:
    """Best-effort resolve of the engine email service (API or agent process)."""
    try:
        from naas_abi import ABIModule

        return ABIModule.get_instance().engine.services.email
    except Exception:
        return None


async def issue_invite_sign_in_challenge(
    auth_service: AuthService,
    email: str,
) -> MagicLinkChallenge | None:
    """Issue OTP + magic-link for an existing (or just-created) invitee."""
    return await auth_service.request_magic_link(email, create_if_missing=False)


async def send_invite_sign_in_email(
    to_email: str,
    challenge: MagicLinkChallenge,
    email_service: EmailService | None,
) -> bool:
    """Send invite sign-in email. Returns True when handed to the email service."""
    query = urlencode({"token": challenge.token})
    magic_link_url = f"{settings.frontend_url.rstrip('/')}{settings.magic_link_path}?{query}"

    if email_service is None:
        if settings.log_otp_codes_when_email_unavailable:
            logger.info(
                "Email service unavailable. Invite sign-in code for %s: %s (link: %s)",
                to_email,
                challenge.otp_code,
                magic_link_url,
            )
        else:
            logger.info(
                "Email service unavailable for invite %s; OTP not logged "
                "(set log_otp_codes_when_email_unavailable=true for local debug)",
                to_email,
            )
        return False

    app_name = settings.magic_link_email_app_name
    template_values = {
        "app_name": app_name,
        "magic_link_url": magic_link_url,
        "otp_code": challenge.otp_code,
        "expire_minutes": settings.magic_link_expire_minutes,
    }
    subject = settings.magic_link_email_subject_template.format_map(
        _SafeTemplateValues(template_values)
    )
    text_body = settings.magic_link_email_text_template.format_map(
        _SafeTemplateValues(template_values)
    )
    html_body = settings.magic_link_email_html_template.format_map(
        _SafeTemplateValues(template_values)
    )
    email_service.send(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        from_email=str(settings.email_from_address),
        from_name=settings.email_from_name,
    )
    return True


async def ensure_user_and_send_invite_email(
    auth_service: AuthService,
    email: str,
    *,
    name: str | None = None,
    email_service: EmailService | None = None,
) -> dict[str, bool]:
    """Create the user if missing, then email OTP/magic-link sign-in."""
    _user, created = await auth_service.ensure_user_for_invite(email, name=name)
    challenge = await issue_invite_sign_in_challenge(auth_service, email)
    sent = False
    if challenge is not None:
        sent = await send_invite_sign_in_email(
            email.lower().strip(),
            challenge,
            email_service if email_service is not None else resolve_email_service(),
        )
    return {"user_created": created, "sign_in_email_sent": sent}
