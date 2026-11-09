"""A user's LinkedIn profile URL and GitHub handle, as Account Settings stores them.

Both are typed by hand, so they arrive in many shapes (no scheme, a country
subdomain, a trailing slash or query, an ``@`` or a full github.com URL). They
are stored in one shape: ``https://www.linkedin.com/in/<vanity>`` and the bare
GitHub username. Anything else is refused (None).
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

_LINKEDIN_HOST = re.compile(r"^([a-z]{2,3}\.)?(www\.)?linkedin\.com$")
_GITHUB_HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def normalize_linkedin_profile_url(value: str) -> str | None:
    """``https://www.linkedin.com/in/<vanity>`` for a profile URL, else None."""
    text = value.strip()
    if not text:
        return None
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        return None
    if not _LINKEDIN_HOST.match((parts.hostname or "").lower()):
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2 or segments[0].lower() not in ("in", "pub"):
        return None
    vanity = unquote(segments[1]).strip().lower()
    if not vanity:
        return None
    return f"https://www.linkedin.com/in/{vanity}"


def normalize_github_handle(value: str) -> str | None:
    """The bare GitHub username in *value* (``@name``, a github.com URL), else None."""
    text = value.strip()
    if "github.com" in text.lower():
        if "://" not in text:
            text = f"https://{text}"
        segments = [segment for segment in urlsplit(text).path.split("/") if segment]
        if len(segments) != 1:
            return None
        text = segments[0]
    text = text.removeprefix("@")
    return text if _GITHUB_HANDLE.match(text) else None
