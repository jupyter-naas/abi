"""Where the built-in IdP is served."""

from __future__ import annotations

IDP_PREFIX = "/idp"


def is_idp_path(path: str) -> bool:
    """The trusted route: its pages carry their own policy and their own cookies,
    which the API's sandboxing of active content and its global CSP would break."""
    return path == IDP_PREFIX or path.startswith(IDP_PREFIX + "/")
