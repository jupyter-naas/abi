"""What the broker user ``module`` may do (docs/adr/20261014_module-identities.md).

Every NATS client logs in (docs/adr/20261008_nats-broker-passwords.md): the engine's
process as ``abi``, with every right, and SDK modules as ``module``, within
:data:`MODULE_PERMISSIONS`. A module may not:

- subscribe to the engine's service and discovery subjects (it would overhear the
  calls and the tokens they carry, or answer in their place), to ``_INBOX.>``, where
  the engine's and Nexus's replies go (modules use ``_INBOX_MODULES``,
  ``naas_abi_sdk.transport``), or to ``$KV.>``;
- publish to ``$KV.>`` (writing a key), create or update a stream (a stream on
  ``abi.svc.>`` would capture the engine's calls), delete or restore one, read one
  with a direct get, or use the JetStream server, meta and account API.

The engine creates the streams modules use (:func:`prepare_module_streams`). A module
still calls every service, serves its own subjects, runs its jobs, stores claim checks,
and uses bus queues whose stream exists.

Still open, with one ``module`` user for every module: a module can subscribe to
another module's subjects (``abi.mod.>``, ``abi.agent.>``) and inbox
(``_INBOX_MODULES.>``), so it sees the requests and replies sent there, and can
replay the tokens sent to that module, to that module, while they last (two
minutes). Through the JetStream consumer API and ``$JS.API.STREAM.MSG.GET`` it can
read any stream, the engine's key-value buckets (``KV_*``) included, and it can purge
any stream and ack or nak any message. Per-module broker users, or NATS accounts, are
the next step. The Docker stack's ``nats.conf`` declares the same lists, and ``abi
dev`` writes them into its own.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

MODULE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "publish": {
        "deny": [
            "$KV.>",
            "$JS.API.STREAM.CREATE.>",
            "$JS.API.STREAM.UPDATE.>",
            "$JS.API.STREAM.DELETE.>",
            "$JS.API.STREAM.MSG.DELETE.>",
            "$JS.API.STREAM.SNAPSHOT.>",
            "$JS.API.STREAM.RESTORE.>",
            "$JS.API.STREAM.PEER.>",
            "$JS.API.STREAM.LEADER.>",
            "$JS.API.META.>",
            "$JS.API.SERVER.>",
            "$JS.API.ACCOUNT.>",
            "$JS.API.DIRECT.GET.>",
        ]
    },
    "subscribe": {"deny": ["abi.svc.>", "abi.discovery.>", "_INBOX.>", "$KV.>"]},
}


def authorization_config(passwords: Mapping[str, str]) -> str:
    """The ``authorization`` block of a nats.conf: ``abi`` with every right and
    ``module`` within MODULE_PERMISSIONS, with their ``passwords`` by user name."""
    users = [
        f"    {{ user: {json.dumps('abi')}, password: {json.dumps(passwords['abi'])} }}",
        (
            f"    {{ user: {json.dumps('module')}, password: {json.dumps(passwords['module'])}, "
            f"permissions: {json.dumps(MODULE_PERMISSIONS)} }}"
        ),
    ]
    return "authorization {\n  users = [\n" + "\n".join(users) + "\n  ]\n}\n"


async def prepare_module_streams(nc: Any, project: str) -> None:
    """Create the streams SDK modules use but may not create: the project's jobs
    stream and the claim-check object store. The engine that hosts discovery runs
    it at start, before any module registers."""
    from naas_abi_sdk import claim_check
    from naas_abi_sdk.job_host import ensure_stream

    await ensure_stream(nc.jetstream(), project)
    await claim_check.ensure_bucket(nc)
