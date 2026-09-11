"""Which responses Nexus pages may frame, and the CSP they get.

``/app-html/`` (bundled module apps) and ``/app-preview/`` (app projects in
the editor) render inside Nexus iframes; everything else is ``DENY``.
"""

from __future__ import annotations

EMBEDDABLE_PREFIXES = ("/app-html/", "/app-preview/")


def is_embeddable(path: str) -> bool:
    return path.startswith(EMBEDDABLE_PREFIXES)


def embed_csp(own: str | None, ancestors: list[str]) -> str:
    """A route's own policy (the preview sandbox) plus ``frame-ancestors``."""
    policy = (own or "").strip().rstrip(";").strip()
    framing = f"frame-ancestors {' '.join(ancestors)};"
    return f"{policy}; {framing}" if policy else framing
