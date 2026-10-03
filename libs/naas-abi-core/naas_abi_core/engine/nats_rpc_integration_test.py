"""Real broker regression tests; requires a local nats-server executable."""

import asyncio
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from threading import Event
from unittest.mock import Mock

import nats
import pytest
from naas_abi_core.engine.nats_rpc import NatsRPCPayloadTooLargeError
from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
    NATSJetStreamAdapter,
)
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter

SECRET = "rpc-integration-test-secret-32-bytes"
pytestmark = pytest.mark.integration


@contextmanager
def nats_server(tmp_path, max_payload):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = tmp_path / "nats.conf"
    config.write_text(f"max_payload: {max_payload}\n")
    with (tmp_path / "nats.log").open("w") as log:
        process = subprocess.Popen(
            [
                binary,
                "-a",
                "127.0.0.1",
                "-p",
                str(port),
                "-c",
                str(config),
                "-js",
                "-sd",
                str(tmp_path / "jetstream"),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail("nats-server exited before accepting connections")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.01)
            else:
                pytest.fail("nats-server did not become ready")
            yield f"nats://127.0.0.1:{port}", max_payload
        finally:
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture(params=[1024, 8 * 1024 * 1024], ids=["small-server-cap", "8MiB"])
def broker(request, tmp_path):
    with nats_server(tmp_path, request.param) as started:
        yield started


def test_oversized_requests_and_replies_fail_then_connection_remains_usable(broker):
    url, limit = broker

    async def scenario():
        nc = await nats.connect(url)
        backend = Mock(spec=IKeyValueAdapter)
        backend.get.return_value = b"x" * limit
        primary = KeyValuePrimaryAdapterNATS(backend, SECRET)
        client = KeyValueSecondaryAdapterNATSClient(url, SECRET, "test")
        try:
            await primary.start(nc)
            await nc.flush()
            with pytest.raises(NatsRPCPayloadTooLargeError):
                await asyncio.to_thread(client.get, "large-reply")
            with pytest.raises(NatsRPCPayloadTooLargeError):
                await asyncio.to_thread(client.set, "large-request", b"x" * limit)
            backend.set.assert_not_called()
            backend.get.return_value = b"still-connected"
            assert await asyncio.to_thread(client.get, "small") == b"still-connected"
        finally:
            await asyncio.to_thread(client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_jetstream_accepted_enqueue_is_not_duplicated_after_lost_ack(
    broker, monkeypatch
):
    url, _ = broker

    async def scenario():
        nc = await nats.connect(url)
        adapter = NATSJetStreamAdapter(url)
        original = adapter._do_enqueue_async

        async def lose_ack(*args):
            await original(*args)
            raise nats.errors.TimeoutError()

        monkeypatch.setattr(adapter, "_do_enqueue_async", lose_ack)
        try:
            with pytest.raises(TimeoutError):
                await asyncio.to_thread(adapter.enqueue, "jobs", "created", b"one")
            info = await nc.jetstream().stream_info(adapter._stream_name("jobs"))
            assert info.state.messages == 1
        finally:
            await asyncio.to_thread(adapter.close)
            await nc.close()

    asyncio.run(scenario())


def test_timeout_does_not_duplicate_a_completed_remote_write(broker):
    url, _ = broker

    async def scenario():
        nc = await nats.connect(url)
        entered, release, finished = Event(), Event(), Event()
        writes = []

        def slow_set(key, value, ttl=None):
            entered.set()
            assert release.wait(2)
            writes.append((key, value))
            finished.set()

        backend = Mock(spec=IKeyValueAdapter)
        backend.set.side_effect = slow_set
        backend.get.return_value = b"ready"
        primary = KeyValuePrimaryAdapterNATS(backend, SECRET)
        client = KeyValueSecondaryAdapterNATSClient(url, SECRET, "test")
        try:
            await primary.start(nc)
            await nc.flush()
            # Warm the connection so the short deadline measures the operation.
            assert await asyncio.to_thread(client.get, "k") == b"ready"
            client._timeout_seconds = 0.1
            with pytest.raises(TimeoutError):
                await asyncio.to_thread(client.set, "k", b"value")
            assert entered.is_set()
            release.set()
            assert await asyncio.to_thread(finished.wait, 2)
            client._timeout_seconds = 2
            assert await asyncio.to_thread(client.get, "k") == b"ready"
            assert writes == [("k", b"value")]
            backend.set.assert_called_once()
        finally:
            release.set()
            await asyncio.to_thread(client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


@pytest.fixture(params=[64 * 1024, 8 * 1024 * 1024], ids=["64KiB", "8MiB"])
def overflow_broker(request, tmp_path):
    with nats_server(tmp_path, request.param) as started:
        yield started


def test_values_above_the_broker_limit_overflow_both_ways(overflow_broker):
    """docs/adr/20261003_nats-rpc-overflow.md, over a real broker."""
    import os

    from naas_abi_core.engine import nats_overflow
    from naas_abi_core.engine.nats_auth import issue_service_token
    from naas_abi_core.engine.nats_overflow import OverflowHost
    from naas_abi_proto.keyvalue.v1 import keyvalue_pb2
    from naas_abi_sdk.transport import Transport

    url, limit = overflow_broker
    value = os.urandom(3 * limit)

    async def scenario():
        nc = await nats.connect(url)
        backend = Mock(spec=IKeyValueAdapter)
        backend.get.return_value = value
        primary = KeyValuePrimaryAdapterNATS(backend, SECRET)
        host = OverflowHost(SECRET)
        client = KeyValueSecondaryAdapterNATSClient(url, SECRET, "test")
        transport = Transport(url, issue_service_token("sdk", SECRET), timeout=10)
        try:
            await primary.start(nc)
            await host.start(nc)
            nats_overflow.install(host)
            await nc.flush()

            assert await asyncio.to_thread(client.get, "large-reply") == value
            await asyncio.to_thread(client.set, "large-request", value)
            assert backend.set.call_args.args[:2] == ("large-request", value)
            reply = await transport.call(
                "abi.svc.keyvalue.v1.get",
                keyvalue_pb2.GetRequest(key="large-reply"),
                keyvalue_pb2.GetResponse,
            )
            assert reply.value == value

            await asyncio.sleep(0.1)  # closes are acknowledged before retiring
            assert host.sessions == {}
            assert (host.parked_bytes, host.buffered_upload_bytes) == (0, 0)
        finally:
            await transport.close()
            await asyncio.to_thread(client.close)
            await host.stop()
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
