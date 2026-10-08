"""Pub/sub and queue messages above the broker limit, against a real nats-server."""

import asyncio
import os
import shutil
import socket
import subprocess
import time

import nats
import pytest

from naas_abi_sdk import claim_check
from naas_abi_sdk.bus import BusClient
from naas_abi_sdk.transport import Transport

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)

LIMIT = 64 * 1024


@pytest.fixture
def broker(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = tmp_path / "nats.conf"
    config.write_text(f"max_payload: {LIMIT}\n")
    process = subprocess.Popen(
        [
            "nats-server",
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-c",
            str(config),
            "-js",
            "-sd",
            str(tmp_path / "js"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"nats://127.0.0.1:{port}"
    process.terminate()
    process.wait(timeout=5)


def test_a_message_that_fits_is_sent_unchanged(broker):
    async def scenario():
        nc = await nats.connect(broker)
        try:
            body, headers = await claim_check.prepare(nc, b"small", {"A": "b"})
            assert (body, headers) == (b"small", {"A": "b"})
        finally:
            await nc.close()

    asyncio.run(scenario())


def test_a_message_above_the_limit_is_stored_and_resolved(broker):
    payload = os.urandom(5 * LIMIT)

    async def scenario():
        nc = await nats.connect(broker)
        try:
            body, headers = await claim_check.prepare(nc, payload, {"A": "b"})
            assert body == b"" and headers["A"] == "b"
            assert claim_check.HEADER in headers
            message = type("Msg", (), {"data": body, "headers": headers})()
            assert await claim_check.resolve(nc, message) == payload
        finally:
            await nc.close()

    asyncio.run(scenario())


def test_values_above_the_cap_are_refused(broker, monkeypatch):
    monkeypatch.setattr(claim_check, "MAX_VALUE_BYTES", 2 * LIMIT)

    async def scenario():
        nc = await nats.connect(broker)
        try:
            with pytest.raises(claim_check.ClaimCheckTooLarge):
                await claim_check.prepare(nc, b"x" * (3 * LIMIT))
        finally:
            await nc.close()

    asyncio.run(scenario())


def test_bus_publish_and_subscribe_carry_payloads_above_the_limit(broker):
    payload = os.urandom(5 * LIMIT)

    async def scenario():
        transport = Transport(broker, "token", timeout=5)
        bus = BusClient(transport)
        try:
            sub = await bus.subscribe("demo", "big")
            await bus.publish("demo", "big", payload)
            await bus.publish("demo", "big", b"small")
            first = await sub.next_msg(timeout=5)
            second = await sub.next_msg(timeout=5)
            return first.data, second.data
        finally:
            await transport.close()

    assert asyncio.run(scenario()) == (payload, b"small")


def test_bus_queues_carry_payloads_above_the_limit_and_at_its_edge(broker):
    # A JetStream publish adds its own header (Nats-Expected-Stream): a body
    # that just fits used to make the server close the connection.
    big = os.urandom(5 * LIMIT)
    edge = os.urandom(LIMIT - 20)

    async def scenario():
        transport = Transport(broker, "token", timeout=5)
        bus = BusClient(transport)
        try:
            await bus.enqueue("jobs", "work", big)
            await bus.enqueue("jobs", "work", edge)
            queue = await bus.dequeue("jobs", "work")
            received = []
            while len(received) < 2:
                for msg in await queue.fetch(1, timeout=5):
                    received.append(msg.data)
                    await msg.ack()
            nc = await transport.connect()
            assert nc.is_connected  # never disconnected by a violation
            return received
        finally:
            await transport.close()

    assert asyncio.run(scenario()) == [big, edge]
