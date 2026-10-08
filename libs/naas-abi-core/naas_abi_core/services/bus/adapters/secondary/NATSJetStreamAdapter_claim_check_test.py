"""Bus messages above the broker limit travel as claim checks (real nats-server)."""

import os
import queue

import pytest
from naas_abi_core.engine.nats_test_server import (
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
    NATSJetStreamAdapter,
)

pytestmark = pytest.mark.skipif(
    nats_server_binary() is None, reason="nats-server not installed"
)
LIMIT = 64 * 1024


@pytest.fixture
def adapter(tmp_path):
    with native_nats_server(tmp_path, max_payload=LIMIT, jetstream=True) as url:
        bus = NATSJetStreamAdapter(url)
        yield bus
        bus.close()


def test_published_messages_above_the_limit_reach_subscribers(adapter):
    received: queue.Queue = queue.Queue()
    adapter.subscribe("events", "big", received.put)
    big = os.urandom(5 * LIMIT)
    # The subscriber connects on its own thread: publish until it is listening.
    for _ in range(50):
        adapter.publish("events", "big", b"ping")
        try:
            if received.get(timeout=0.1) == b"ping":
                break
        except queue.Empty:
            continue

    adapter.publish("events", "big", big)

    assert received.get(timeout=10) == big


def test_queued_messages_above_the_limit_and_at_its_edge_are_delivered(adapter):
    big = os.urandom(5 * LIMIT)
    edge = os.urandom(LIMIT - 20)  # fits alone, not with the stream header
    adapter.enqueue("work", "item", big)
    adapter.enqueue("work", "item", edge)
    adapter.enqueue("work", "item", b"small")
    received: queue.Queue = queue.Queue()

    adapter.dequeue("work", "item", received.put)

    assert [received.get(timeout=10) for _ in range(3)] == [big, edge, b"small"]
