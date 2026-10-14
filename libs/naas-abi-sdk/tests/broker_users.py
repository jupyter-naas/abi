"""Brokers as deployed, for the SDK's real-broker suites.

``open``: anyone connects with every right. ``module-user``: every client logs in,
and the suite connects as ``module``, within the engine's MODULE_PERMISSIONS
(naas_abi_core.engine.nats_permissions), as SDK modules do in a project. It needs
ABI core for that definition, so the SDK's isolated runs skip it.
"""

from __future__ import annotations

import pytest

KINDS = ("open", "module-user")
PASSWORDS = {"abi": "nats-abi-tests", "module": "nats-module-tests"}


def config(kind: str) -> str:
    """nats.conf lines admitting the deployed users, or none for ``open``."""
    if kind == "open":
        return ""
    permissions = pytest.importorskip("naas_abi_core.engine.nats_permissions")
    return permissions.authorization_config(PASSWORDS)


def login(url: str, kind: str) -> str:
    """``url`` as the suite connects to it: logged in as ``module`` if users are on."""
    if kind == "open":
        return url
    return url.replace("nats://", f"nats://module:{PASSWORDS['module']}@", 1)


def as_engine(url: str) -> str:
    """``url`` logged in as ``abi`` instead (every right), for what an operator
    or the engine does in a test, such as deleting a stream."""
    module = f"module:{PASSWORDS['module']}@"
    return url.replace(module, f"abi:{PASSWORDS['abi']}@", 1)
