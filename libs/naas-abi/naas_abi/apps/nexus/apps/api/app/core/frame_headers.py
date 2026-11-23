"""Which responses Nexus pages may frame, and the CSP they get.

``/app-html/`` (bundled module apps), ``/app-preview/`` (app projects in the
editor) and ``/app-remote/`` (apps of remote modules) render inside Nexus
iframes; everything else is ``DENY``. Their ``frame-ancestors`` lists
``'self'`` and the configured origins that are valid ``http(s)://host[:port]``
origins: a ``*``, a wildcard host or an entry carrying a directive of its own
never reaches the header.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

EMBEDDABLE_PREFIXES = ("/app-html/", "/app-preview/", "/app-remote/")


def is_embeddable(path: str) -> bool:
    return path.startswith(EMBEDDABLE_PREFIXES)


# ``scheme://host[:port]`` with an optional trailing ``/``, after the CSP
# host-source grammar: http(s) only, labels of letters, digits and ``-``, no
# ``*``, no IPv6 literal, no userinfo. Nothing else may follow, so an entry
# cannot carry a path, a query, a fragment, a second source or a directive.
_ORIGIN = re.compile(
    r"(?P<origin>https?://[a-z0-9-]+(?:\.[a-z0-9-]+)*(?::[0-9]+)?)/?",
    re.IGNORECASE | re.ASCII,
)


def frame_origin(value: object) -> str | None:
    """The origin ``value`` names, lower-cased, or ``None`` when it is not one.

    Surrounding whitespace is stripped and one trailing ``/`` dropped; anything
    else (``*``, a wildcard host, whitespace, ``;``, ``,``, a path, a query, a
    fragment, userinfo, another scheme) rejects the entry.
    """
    if not isinstance(value, str):
        return None
    match = _ORIGIN.fullmatch(value.strip())
    return match.group("origin").lower() if match else None


def frame_ancestors(frontend_url: str | None, cors_origins: Iterable[str]) -> list[str]:
    """Who may frame an embeddable path: ``'self'``, Nexus and the CORS origins.

    Built from configuration only. The origin a request names in ``Origin`` or
    ``Referer`` is never added: any page could name itself. Only entries that
    are an ``http(s)://host[:port]`` origin are kept (``frame_origin``), in
    order and once each; the rest are named once at startup
    (``ignored_frame_origins``).
    """
    ancestors = ["'self'"]
    for entry in (frontend_url, *cors_origins):
        origin = frame_origin(entry)
        if origin and origin not in ancestors:
            ancestors.append(origin)
    return ancestors


def ignored_frame_origins(frontend_url: str | None, cors_origins: Iterable[str]) -> list[str]:
    """The configured entries ``frame_ancestors`` drops, blanks left out."""
    return [
        entry
        for entry in (frontend_url, *cors_origins)
        if entry is not None and str(entry).strip() and frame_origin(entry) is None
    ]


def embed_csp(own: str | None, ancestors: list[str]) -> str:
    """A route's own policy (the preview sandbox) plus ``frame-ancestors``."""
    policy = (own or "").strip().rstrip(";").strip()
    framing = f"frame-ancestors {' '.join(ancestors)};"
    return f"{policy}; {framing}" if policy else framing
