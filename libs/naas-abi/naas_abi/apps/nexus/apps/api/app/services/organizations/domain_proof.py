"""Proof that an organization controls an email domain: a DNS TXT record.

An organization claims a domain and is given a token (``domain_token``: derived from
the organization and the domain, so claiming again gives the same one). It proves
control by publishing ``_nexus-verify.<domain>`` as a TXT record holding the token;
Nexus reads it server-side (``proven``). Public mail domains (``gmail.com``...) are
never an organization's (``is_public_mail_domain``).
"""

from __future__ import annotations

import hashlib

from starlette.concurrency import run_in_threadpool

PROOF_LABEL = "_nexus-verify"
_LOOKUP_SECONDS = 5.0

# Mail providers whose addresses belong to their users, never to an organization.
PUBLIC_MAIL_DOMAINS = frozenset(
    {
        "aol.com",
        "fastmail.com",
        "gmail.com",
        "gmx.com",
        "gmx.de",
        "gmx.fr",
        "gmx.net",
        "googlemail.com",
        "hey.com",
        "hotmail.com",
        "hotmail.fr",
        "icloud.com",
        "laposte.net",
        "live.com",
        "mail.com",
        "mail.ru",
        "me.com",
        "msn.com",
        "orange.fr",
        "outlook.com",
        "outlook.fr",
        "pm.me",
        "proton.me",
        "protonmail.com",
        "qq.com",
        "sfr.fr",
        "tutanota.com",
        "web.de",
        "yahoo.com",
        "yahoo.fr",
        "yandex.com",
        "yandex.ru",
        "zoho.com",
        "163.com",
        "126.com",
    }
)


def is_public_mail_domain(domain: str) -> bool:
    """A public mail provider's domain, or a name that is no organization's (no dot)."""
    name = domain.strip().lower().rstrip(".")
    return "." not in name or name in PUBLIC_MAIL_DOMAINS


def domain_token(org_id: str, domain: str) -> str:
    """The TXT value proving ``org_id`` controls ``domain``: the same at every claim."""
    digest = hashlib.sha256(f"nexus-domain\n{org_id}\n{domain.lower()}".encode()).hexdigest()
    return f"nexus-domain-verification={digest[:40]}"


def proof_name(domain: str) -> str:
    return f"{PROOF_LABEL}.{domain.lower().rstrip('.')}"


def txt_records(name: str) -> list[str]:
    """The TXT values published at ``name``; none when it has none or the lookup fails."""
    try:
        import dns.resolver
    except ImportError:  # pragma: no cover - dnspython comes with email-validator
        return []
    try:
        answer = dns.resolver.resolve(name, "TXT", lifetime=_LOOKUP_SECONDS)
    except Exception:  # noqa: BLE001 - no record, no answer, no proof
        return []
    values: list[str] = []
    for record in answer:
        values.append(b"".join(getattr(record, "strings", ())).decode("utf-8", "replace"))
    return values


async def proven(domain: str, token: str | None) -> bool:
    """Whether ``domain`` publishes ``token`` at its proof name."""
    if not token:
        return False
    found = await run_in_threadpool(txt_records, proof_name(domain))
    return any(value.strip() == token for value in found)
