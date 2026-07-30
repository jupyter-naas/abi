"""Absolute URLs built from ``global_config.public_api_host``.

Module public assets (agent logos, app avatars, …) are mounted on the core API
at ``/modules/<path>``. Callers that return those URLs to the frontend must
prefix them with the public API host so ``<img>`` tags resolve regardless of
the web origin.
"""

from __future__ import annotations


def public_api_host() -> str | None:
    """Configured public API host, normalized with an ``https://`` scheme.

    Returns ``None`` when the ABIModule instance is not initialized (e.g. unit
    tests), so callers can fall back to a relative path.
    """
    try:
        from naas_abi import ABIModule

        host = ABIModule.get_instance().configuration.global_config.public_api_host
    except Exception:
        return None
    if not isinstance(host, str) or not host:
        return None
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return host.rstrip("/")


def public_modules_url(path: str) -> str:
    """Absolute public-API URL for a module asset under ``/modules/<path>``.

    Raises if ``public_api_host`` cannot be resolved (same failure mode the
    agents adapter historically had when ABIModule was unavailable). Soft
    callers should use :func:`public_api_host` and handle ``None`` instead.
    """
    host = public_api_host()
    if host is None:
        # Re-raise via get_instance() when uninitialized; otherwise host is empty.
        from naas_abi import ABIModule

        ABIModule.get_instance()
        raise RuntimeError("global_config.public_api_host is not configured")
    return f"{host}/modules/{path.lstrip('/')}"
