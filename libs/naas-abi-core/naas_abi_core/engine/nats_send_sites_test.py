"""Every raw NATS send in core, the SDK and Nexus, and why it fits the broker.

The broker's max_payload (8 MB in nats.conf / abi dev) counts the body AND the
header block; nats-py only checks the body, and a message over the limit makes
the server close the connection. Sends must go through a size-aware path:
RPC overflow (nats_rpc.py, sdk transport.py), transfer streams, claim checks
(sdk claim_check.py) or messages.reply, or be bounded by construction.

A new raw send fails this test: route it through one of those helpers, or add
it here with the reason it can never exceed the limit.
(docs/adr/20261003_nats-rpc-overflow.md, docs/adr/20261003_nats-claim-check.md)
"""

import re
from pathlib import Path

LIBS = Path(__file__).resolve().parents[3]
ROOTS = (
    "naas-abi-core/naas_abi_core",
    "naas-abi-sdk/naas_abi_sdk",
    "naas-abi/naas_abi/apps/nexus/apps/api",
)
SEND = re.compile(
    r"(?<![\w.])(?:self\.)?_?(?:nc|js|nats_client|connection|client)\.(?:publish|request)\("
    r"|\.jetstream\(\)\.publish\("
    r"|\b(?:msg|request|req)\.respond(?:_error)?\("
    r"|\._client\.publish\("
    r"|\bbucket\.(?:put|update|create)\("
    r"|_bucket\(nc\)\)\.put\("
)

REVIEWED = {
    "naas-abi-core/naas_abi_core/engine/nats_overflow.py": (
        1,
        "overflow fetch: transfer read/start/close requests, a few bytes each",
    ),
    "naas-abi-core/naas_abi_core/engine/nats_rpc.py": (
        3,
        (
            "RPC replies sized with their headers against the connection's limit "
            "(parked or refused above it); requests are checked the same way, then "
            "sent through no_responders"
        ),
    ),
    "naas-abi-core/naas_abi_core/engine/ownership/adapters/secondary/lease_jetstream.py": (
        2,
        "engine lease record: one holder description, a few hundred bytes",
    ),
    "naas-abi-core/naas_abi_core/services/bus/adapters/secondary/NATSJetStreamAdapter.py": (
        2,
        "bus publish/enqueue: claim_check.prepare (JetStream header reserved)",
    ),
    "naas-abi-core/naas_abi_core/services/discovery/adapters/secondary/discovery_jetstream.py": (
        1,
        "discovery registry snapshot: at most 512 KiB (DiscoveryService, KV max_value_size)",
    ),
    "naas-abi-sdk/naas_abi_sdk/agent_host.py": (
        1,
        (
            "RunUpdate to a submitter's inbox: event data inline only up to "
            "min(32 KiB, a quarter of the broker limit), else its part count"
        ),
    ),
    "naas-abi-sdk/naas_abi_sdk/bus.py": (
        2,
        "bus publish/enqueue: claim_check.prepare (JetStream header reserved)",
    ),
    "naas-abi-sdk/naas_abi_sdk/claim_check.py": (
        1,
        "object store put: chunks sized to half the broker limit",
    ),
    "naas-abi-sdk/naas_abi_sdk/job_host.py": (
        2,
        (
            "schedule messages carry b'{}'; the event bridge's trigger goes through "
            "claim_check.prepare"
        ),
    ),
    "naas-abi-sdk/naas_abi_sdk/jobs.py": (
        2,
        "run cancellation carries the run id; triggers go through claim_check.prepare",
    ),
    "naas-abi-sdk/naas_abi_sdk/messages.py": (
        1,
        "reply(): refuses a message over the limit, headers counted",
    ),
    "naas-abi-sdk/naas_abi_sdk/no_responders.py": (
        2,
        (
            "resends a request nobody received; its callers (nats_rpc, Transport) "
            "check the size with headers first, and overflow above the limit"
        ),
    ),
    "naas-abi/naas_abi/apps/nexus/apps/api/app/services/sysadmin/adapters/secondary/nats_micro.py": (
        1,
        "$SRV.STATS request: empty body",
    ),
}


def _sends() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for root in ROOTS:
        for path in (LIBS / root).rglob("*.py"):
            if (
                path.name.endswith("_test.py")
                or path.name.startswith("test_")
                or "tests" in path.parts
                or "node_modules" in path.parts
            ):
                continue
            for number, line in enumerate(
                path.read_text(errors="ignore").splitlines(), 1
            ):
                if SEND.search(line) and not line.lstrip().startswith("#"):
                    key = path.relative_to(LIBS).as_posix()
                    found.setdefault(key, []).append(f"{number}: {line.strip()}")
    return found


def test_every_raw_nats_send_is_reviewed_for_the_broker_limit():
    found = _sends()
    unreviewed = {
        path: lines
        for path, lines in found.items()
        if len(lines) != REVIEWED.get(path, (0, ""))[0]
    }
    stale = sorted(set(REVIEWED) - set(found))
    assert not unreviewed and not stale, (
        "Raw NATS sends changed. Route new ones through overflow, transfer, "
        "claim_check or messages.reply, or review them in REVIEWED with the "
        f"reason they fit the broker limit.\nChanged: {unreviewed}\nGone: {stale}"
    )
