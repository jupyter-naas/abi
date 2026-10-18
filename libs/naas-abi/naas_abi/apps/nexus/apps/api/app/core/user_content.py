"""Headers for bytes a user supplied, served from the API origin.

The API origin carries the session cookie, so a page a member uploaded (an SVG
or HTML file with a script) must never run there: it would act as whoever opens
it. Two layers keep it inert:

* a route that serves user bytes sends ``user_content_headers``: a sandbox
  policy (an opaque origin, no scripts), ``nosniff``, and ``attachment`` for
  active types, which a browser downloads instead of rendering;
* ``harden_active_content`` is the net under every other API route: whatever
  returns an active type gets the same, unless the route is a sandboxed app
  (``/app-html``, ``/app-preview``, ``/app-remote``) with a policy of its own.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from naas_abi.apps.nexus.apps.api.app.core.content_disposition import content_disposition

SANDBOX = "sandbox"

_ACTIVE_MEDIA_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "image/svg+xml",
        "text/xml",
        "application/xml",
        "text/xsl",
        "text/javascript",
        "application/javascript",
        "application/x-javascript",
        "application/ecmascript",
        "text/ecmascript",
    }
)


def is_active_media_type(content_type: str | None) -> bool:
    """Whether a browser may run what this type names: markup, SVG or script."""
    base = (content_type or "").split(";", 1)[0].strip().lower()
    return base in _ACTIVE_MEDIA_TYPES or base.endswith(("+xml", "/xml"))


def user_content_headers(filename: str, media_type: str | None) -> dict[str, str]:
    """The headers of a route that serves a user's file to whoever may read it."""
    disposition = "attachment" if is_active_media_type(media_type) else "inline"
    return {
        "Content-Disposition": content_disposition(disposition, filename),
        "Content-Security-Policy": SANDBOX,
        "X-Content-Type-Options": "nosniff",
    }


def with_sandbox(policy: str | None) -> str:
    """``policy`` with the sandbox directive in front, once."""
    existing = (policy or "").strip().rstrip(";").strip()
    if not existing:
        return SANDBOX
    if any(part.strip().split(" ", 1)[0] == SANDBOX for part in existing.split(";")):
        return existing
    return f"{SANDBOX}; {existing}"


def harden_active_content(headers: MutableMapping[str, str] | Mapping[str, str]) -> None:
    """Sandbox a response of an active type and make it a download."""
    if not is_active_media_type(headers.get("content-type")):
        return
    headers["Content-Security-Policy"] = with_sandbox(headers.get("content-security-policy"))  # type: ignore[index]
    disposition = headers.get("content-disposition")
    if not disposition:
        headers["Content-Disposition"] = "attachment"  # type: ignore[index]
    elif disposition.lower().startswith("inline"):
        headers["Content-Disposition"] = "attachment" + disposition[len("inline") :]  # type: ignore[index]
