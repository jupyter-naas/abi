"""Absolute URLs built from ``global_config.public_api_host``.

Module public assets (agent logos, app avatars, …) are mounted on the core API
at ``/modules/<path>``. Callers that return those URLs to the frontend must
prefix them with the public API host so ``<img>`` tags resolve regardless of
the web origin.
"""

from __future__ import annotations

import os


def _strip_scheme(host: str) -> str:
    value = host.strip()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def _is_loopback_hostname(host: str) -> bool:
    hostname = _strip_scheme(host).split("/", 1)[0].split(":", 1)[0]
    return hostname in {"localhost", "127.0.0.1"}


def _with_scheme(host: str) -> str:
    value = host.strip().rstrip("/")
    if value.startswith(("http://", "https://")):
        return value
    scheme = "http" if _is_loopback_hostname(value) else "https"
    return f"{scheme}://{value}"


def resolve_public_api_host(
    configured: str | None,
    *,
    abi_port: str | None = None,
    browser_host: str | None = None,
    dev_origin: str | None = None,
) -> str | None:
    """Pick the origin browsers should use for ``/modules`` and ``/logos``.

    ``dev_origin`` (``ABI_DEV_PUBLIC_API_ORIGIN``) wins. ``abi dev up`` sets it
    on the process so a ``.env`` public hostname cannot shadow the allocated
    port. Docker and remote leave it unset.

    Without that, a public hostname in config is left alone. A loopback
    (any port) plus ``ABI_PORT`` uses the live bind.
    """
    origin = (dev_origin or "").strip()
    if origin:
        return _with_scheme(origin)

    configured = (configured or "").strip() or None
    port = (abi_port or "").strip()

    if configured and not _is_loopback_hostname(configured):
        return _with_scheme(configured)

    if port.isdigit():
        host = (browser_host or "").strip() or "localhost"
        return f"http://{host}:{port}"

    if configured:
        return _with_scheme(configured)
    return None


def public_api_host() -> str | None:
    """Configured public API host, with a scheme.

    Returns ``None`` when the ABIModule instance is not initialized (e.g. unit
    tests) and no live-port override is set, so callers can fall back to a
    relative path.
    """
    configured: str | None = None
    try:
        from naas_abi import ABIModule

        value = ABIModule.get_instance().configuration.global_config.public_api_host
        if isinstance(value, str) and value.strip():
            configured = value
    except Exception:
        configured = None

    return resolve_public_api_host(
        configured,
        abi_port=os.environ.get("ABI_PORT"),
        browser_host=os.environ.get("ABI_DEV_BROWSER_HOST"),
        dev_origin=os.environ.get("ABI_DEV_PUBLIC_API_ORIGIN"),
    )


def public_modules_url(path: str) -> str:
    """Absolute public-API URL for a module asset under ``/modules/<path>``.

    Raises if ``public_api_host`` cannot be resolved (same failure mode the
    agents adapter historically had when ABIModule was unavailable). Soft
    callers should use :func:`public_api_host` and handle ``None`` instead.
    """
    host = public_api_host()
    if host is None:
        from naas_abi import ABIModule

        ABIModule.get_instance()
        raise RuntimeError("global_config.public_api_host is not configured")
    return f"{host}/modules/{path.lstrip('/')}"
