"""What the broker user ``module`` may do (docs/adr/20261014_module-identities.md).

Every NATS client logs in (docs/adr/20261008_nats-broker-passwords.md): the engine's
process as ``abi``, with every right, and SDK modules as ``module``, within
:data:`MODULE_PERMISSIONS`. A module may not listen on the engine's service and
discovery subjects (it would overhear the calls and the tokens they carry, or answer
in their place), use the engine's key-value buckets directly, or delete or restore
streams. It still calls every service, serves its own subjects, runs its jobs and
stores claim checks.

All modules share the user, so one module can still listen on another's subjects;
per-module broker users (or auth callout) are the next step. The Docker stack's
``nats.conf`` declares the same lists, and ``abi dev`` writes them into its own.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

MODULE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "publish": {
        "deny": [
            "$KV.>",
            "$JS.API.STREAM.DELETE.>",
            "$JS.API.STREAM.MSG.DELETE.>",
            "$JS.API.STREAM.SNAPSHOT.>",
            "$JS.API.STREAM.RESTORE.>",
            "$JS.API.STREAM.PEER.>",
            "$JS.API.STREAM.LEADER.>",
            "$JS.API.META.>",
            "$JS.API.SERVER.>",
            "$JS.API.ACCOUNT.>",
        ]
    },
    "subscribe": {"deny": ["abi.svc.>", "abi.discovery.>", "$KV.>"]},
}


def authorization_config(passwords: Mapping[str, str]) -> str:
    """The ``authorization`` block of a nats.conf: ``abi`` with every right and
    ``module`` within MODULE_PERMISSIONS, with their ``passwords`` by user name."""
    users = [
        f"    {{ user: {json.dumps('abi')}, password: {json.dumps(passwords['abi'])} }}",
        f"    {{ user: {json.dumps('module')}, password: {json.dumps(passwords['module'])}, "
        f"permissions: {json.dumps(MODULE_PERMISSIONS)} }}",
    ]
    return "authorization {\n  users = [\n" + "\n".join(users) + "\n  ]\n}\n"
