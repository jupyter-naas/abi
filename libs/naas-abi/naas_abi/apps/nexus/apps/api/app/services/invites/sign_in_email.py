"""Shared invite sign-in email (magic link + OTP) for org/workspace invites."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService, MagicLinkChallenge
from naas_abi_core.services.email.EmailPorts import EmailAttachment
from naas_abi_core.services.email.EmailService import EmailService

logger = logging.getLogger(__name__)

SIGN_IN_LOGO_CID = "sign-in-logo"


class _SafeTemplateValues(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def magic_link_url_for_token(token: str) -> str:
    query = urlencode({"token": token})
    return f"{settings.frontend_url.rstrip('/')}{settings.magic_link_path}?{query}"


def _is_private_email_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    host = hostname.lower().rstrip(".")
    private_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "abi", "::1"}  # nosec B104 - hostname comparison, not a socket bind
    return (
        host in private_hosts
        or host.endswith(".localhost")
        or host.endswith(".local")
    )


def _guess_mime_type(url_or_name: str, content: bytes) -> str:
    mime, _ = mimetypes.guess_type(url_or_name)
    if mime and mime.startswith("image/"):
        return mime
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:2] == b"\xff\xd8":
        return "image/jpeg"
    if content[:4] == b"GIF8":
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _logo_fetch_candidates(logo_url: str) -> list[str]:
    """Prefer loopback HTTP for private hosts so we can CID-embed the bytes."""
    parsed = urlparse(logo_url)
    path = parsed.path or "/"
    candidates: list[str] = []
    if _is_private_email_host(parsed.hostname):
        # Same process / Docker network — email clients cannot reach *.localhost.
        candidates.extend(
            [
                f"http://127.0.0.1:9879{path}",
                f"http://abi:9879{path}",
            ]
        )
    candidates.append(logo_url)
    # De-dupe while preserving order; only http(s) is fetchable (tenant config is
    # not trusted to keep file:/ or custom schemes out of the logo URL).
    seen: set[str] = set()
    ordered: list[str] = []
    for url in candidates:
        if url in seen or urlparse(url).scheme not in ("http", "https"):
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _try_load_seal_from_disk(logo_url: str) -> bytes | None:
    """Load the CBP seal from the report module assets when the logo URL points at it."""
    seal_name = "Seal_of_U.S._Customs_and_Border_Protection.png"
    if seal_name not in logo_url:
        return None

    candidates: list[Path] = []
    try:
        import report as report_module

        report_root = Path(report_module.__file__).resolve().parent
        candidates.append(report_root / "assets" / "public" / seal_name)
    except Exception:
        pass

    cwd = Path.cwd()
    for base in (cwd, *cwd.parents[:4]):
        candidates.append(base / "src" / "report" / "assets" / "public" / seal_name)
        candidates.append(base / "report" / "assets" / "public" / seal_name)

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            if resolved.is_file():
                return resolved.read_bytes()
        except OSError:
            continue
    return None


def _load_logo_bytes(logo_url: str) -> bytes | None:
    """Load logo bytes for CID embedding (required when URL is not public)."""
    if not logo_url:
        return None

    disk = _try_load_seal_from_disk(logo_url)
    if disk:
        return disk

    for url in _logo_fetch_candidates(logo_url):
        try:
            request = Request(url, headers={"User-Agent": "nexus-sign-in-email/1.0"})
            with urlopen(request, timeout=5) as response:  # nosec B310 - http(s)-only candidates
                data = response.read()
                if data:
                    return data
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            logger.debug("Sign-in email logo fetch failed for %s: %s", url, exc)
    return None


def render_sign_in_email(
    *,
    magic_link_url: str,
    otp_code: str,
) -> tuple[str, str, str, list[EmailAttachment]]:
    """Render subject/text/html + inline logo attachments for a sign-in email."""
    tenant = settings.tenant
    logo_url = tenant.logo_rectangle_url or tenant.logo_url or ""
    attachments: list[EmailAttachment] = []
    logo_html = ""

    if logo_url:
        logo_bytes = _load_logo_bytes(logo_url)
        if logo_bytes:
            mime = _guess_mime_type(logo_url, logo_bytes)
            ext = mimetypes.guess_extension(mime) or ".png"
            attachments.append(
                EmailAttachment(
                    filename=f"logo{ext}",
                    content=logo_bytes,
                    mime_type=mime,
                    content_id=SIGN_IN_LOGO_CID,
                    is_inline=True,
                )
            )
            logo_src = f"cid:{SIGN_IN_LOGO_CID}"
        else:
            # Public absolute URL fallback (clients may still block external images).
            logo_src = logo_url if not _is_private_email_host(urlparse(logo_url).hostname) else ""
        if logo_src:
            logo_html = (
                f'<img src="{logo_src}" alt="{settings.magic_link_email_app_name}" '
                'width="96" height="96" '
                'style="display:block;max-width:96px;height:auto;'
                'margin:0 auto;border:0;outline:none;text-decoration:none;" />'
            )

    footer_text = tenant.login_footer_text or ""
    template_values = {
        "app_name": settings.magic_link_email_app_name,
        "magic_link_url": magic_link_url,
        "otp_code": otp_code,
        "expire_minutes": settings.magic_link_expire_minutes,
        "primary_color": tenant.primary_color,
        "accent_color": tenant.accent_color,
        "background_color": tenant.background_color,
        "login_card_color": tenant.login_card_color,
        "login_input_color": tenant.login_input_color,
        "login_border_radius": tenant.login_border_radius,
        "login_footer_text": footer_text,
        "logo_url": logo_url,
        "logo_html": logo_html,
        "tab_title": tenant.tab_title,
    }
    safe = _SafeTemplateValues(template_values)
    subject = settings.magic_link_email_subject_template.format_map(safe)
    text_body = settings.magic_link_email_text_template.format_map(safe)
    html_body = settings.magic_link_email_html_template.format_map(safe)
    return subject, text_body, html_body, attachments


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
    magic_link_url = magic_link_url_for_token(challenge.token)

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

    subject, text_body, html_body, attachments = render_sign_in_email(
        magic_link_url=magic_link_url,
        otp_code=challenge.otp_code,
    )
    email_service.send(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        from_email=str(settings.email_from_address),
        from_name=settings.email_from_name,
        attachments=attachments or None,
    )
    return True


async def issue_and_send_invite_sign_in(
    auth_service: AuthService,
    email: str,
    *,
    email_service: EmailService | None = None,
) -> bool:
    """Issue the invite sign-in challenge and email it, or leave nothing behind.

    A challenge the invitee never received is worse than no challenge: it stays
    valid until it expires and, because sign-in accepts any active challenge, it
    widens the window on a code nobody delivered. So any delivery failure — raised
    or reported by returning False — invalidates the challenge before propagating.

    Callers that already created the user (the org and workspace invite routes)
    use this directly; ensure_user_and_send_invite_email wraps it with creation.
    """
    challenge = await issue_invite_sign_in_challenge(auth_service, email)
    if challenge is None:
        return False
    try:
        sent = await send_invite_sign_in_email(
            email.lower().strip(),
            challenge,
            email_service if email_service is not None else resolve_email_service(),
        )
    except Exception:
        await auth_service.invalidate_magic_link_challenge(challenge.token_id)
        raise
    if not sent:
        await auth_service.invalidate_magic_link_challenge(challenge.token_id)
    return sent


async def ensure_user_and_send_invite_email(
    auth_service: AuthService,
    email: str,
    *,
    name: str | None = None,
    email_service: EmailService | None = None,
) -> dict[str, bool]:
    """Create the user if missing, then email OTP/magic-link sign-in."""
    _user, created = await auth_service.ensure_user_for_invite(email, name=name)
    sent = await issue_and_send_invite_sign_in(
        auth_service, email, email_service=email_service
    )
    return {"user_created": created, "sign_in_email_sent": sent}
