"""NATS connection names: ``<role>@<host>``, so the broker's /connz shows who is who."""

from __future__ import annotations

import re
import socket

_SUFFIX = re.compile(r"(SecondaryAdapter)?NATS(Client)?$")


def connection_name(role: str) -> str:
    return f"{role}@{socket.gethostname()}"


def rpc_client_role(service_identity: str, client_type: type) -> str:
    """``abi-<identity>:<domain>`` from e.g. ``ObjectStorageSecondaryAdapterNATSClient``."""
    domain = _SUFFIX.sub("", client_type.__name__)
    domain = re.sub(r"(?<!^)(?=[A-Z])", "_", domain).lower()
    return f"abi-{service_identity}:{domain}"
