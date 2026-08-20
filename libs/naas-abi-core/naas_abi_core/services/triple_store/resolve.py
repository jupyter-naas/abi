"""Resolve local ``abi dev`` runtime settings for standalone scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_ABI_DEV_INSTANCE_REL = Path(".abi") / "dev" / "instance.json"


def local_probe_host() -> str:
    """Server-to-server dial target for services started by ``abi dev up``."""
    host = os.environ.get("ABI_DEV_BIND_HOST") or "127.0.0.1"
    if host in ("0.0.0.0", "::", "*"):
        return "127.0.0.1"
    return host


def load_abi_dev_instance(*, start: Path | None = None) -> dict[str, Any] | None:
    """Return ``abi dev`` instance metadata for the nearest project root."""
    anchor = (start or Path.cwd()).resolve()
    for candidate in (anchor, *anchor.parents):
        instance_path = candidate / _ABI_DEV_INSTANCE_REL
        if not instance_path.is_file():
            continue
        try:
            payload = json.loads(instance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload
    return None


def abi_dev_service_port(service: str, *, start: Path | None = None) -> int | None:
    """Return the allocated local port for *service*, if ``abi dev`` metadata exists."""
    instance = load_abi_dev_instance(start=start)
    if instance is None:
        return None
    ports = instance.get("ports")
    if not isinstance(ports, dict):
        return None
    port = ports.get(service)
    if port is None:
        return None
    try:
        return int(port)
    except (TypeError, ValueError):
        return None


def resolve_local_http_url(
    service: str,
    *,
    env_var: str | None = None,
    default_url: str,
    start: Path | None = None,
) -> str:
    """Resolve a local HTTP service URL from env, ``abi dev`` ports, then *default_url*."""
    if env_var:
        explicit = os.environ.get(env_var)
        if explicit:
            return explicit
    port = abi_dev_service_port(service, start=start)
    if port is not None:
        return f"http://{local_probe_host()}:{port}"
    return default_url
