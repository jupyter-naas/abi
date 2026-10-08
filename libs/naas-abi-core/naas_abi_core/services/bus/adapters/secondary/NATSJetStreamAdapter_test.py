import asyncio
import threading
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import nats
import pytest
from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
    NATSJetStreamAdapter,
)
from naas_abi_core.services.bus.tests.bus__secondary_adapter__generic_test import (
    GenericBusSecondaryAdapterTest,
)
from naas_abi_sdk import lifeline
from nats.errors import ConnectionClosedError, MaxPayloadError
from nats.errors import TimeoutError as NatsTimeoutError


class TestNATSJetStreamAdapter(GenericBusSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return NATSJetStreamAdapter


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    NATSJetStreamAdapter("nats://127.0.0.1:4222")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")
    adapter.close()  # must not raise, must not connect


def test_context_manager_calls_close(monkeypatch):
    closed = []
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")
    monkeypatch.setattr(adapter, "close", lambda: closed.append(True))

    with adapter:
        pass

    assert closed == [True]


@pytest.mark.parametrize("method", ["publish", "enqueue"])
@pytest.mark.parametrize(
    "error", [NatsTimeoutError(), ConnectionClosedError(), MaxPayloadError()]
)
def test_failed_send_is_not_replayed(method, error, monkeypatch):
    with NATSJetStreamAdapter() as adapter:
        operation = AsyncMock(side_effect=error)
        monkeypatch.setattr(adapter, f"_do_{method}_async", operation)
        with pytest.raises(type(error)):
            getattr(adapter, method)("topic", "key", b"payload")
        assert operation.await_count == 1


# ---------------------------------------------------------------------------
# Pure helpers -- routing-key translation and deterministic naming. These are
# plain functions with no broker interaction, so unlike the bridging itself
# they're worth unit testing directly rather than only through integration.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("routing_key", "expected"),
    [
        ("#", ">"),
        ("system.#", "system.>"),
        ("user.*", "user.*"),
        ("user.created", "user.created"),
        ("*", "*"),
    ],
)
def test_to_nats_pattern_translates_hash_to_greater_than(routing_key, expected):
    assert NATSJetStreamAdapter._to_nats_pattern(routing_key) == expected


def test_to_nats_pattern_leaves_non_trailing_hash_literal():
    # '#' outside the trailing position has no direct NATS equivalent -- it
    # is matched literally instead of as a wildcard (a warning is logged;
    # see _to_nats_pattern's docstring for the documented gap).
    result = NATSJetStreamAdapter._to_nats_pattern("system.#.critical")
    assert result == "system.#.critical"


def test_stream_name_has_no_invalid_nats_characters():
    name = NATSJetStreamAdapter._stream_name("evt.x")
    assert not any(c in name for c in ">*. /\\")


def test_stream_name_is_deterministic_per_topic():
    assert NATSJetStreamAdapter._stream_name(
        "topic"
    ) == NATSJetStreamAdapter._stream_name("topic")
    assert NATSJetStreamAdapter._stream_name(
        "topic.a"
    ) != NATSJetStreamAdapter._stream_name("topic.b")


def test_durable_consumer_name_is_deterministic_per_topic_and_routing_key():
    name_a = NATSJetStreamAdapter._durable_consumer_name("topic", "routing.key")
    name_b = NATSJetStreamAdapter._durable_consumer_name("topic", "routing.key")
    name_c = NATSJetStreamAdapter._durable_consumer_name("topic", "other.key")

    assert name_a == name_b
    assert name_a != name_c
    assert not any(c in name_a for c in ">*. /\\")


# ---------------------------------------------------------------------------
# Real integration tests against a live NATS/JetStream container.
#
# The async bridge (persistent publish loop, per-call consumer threads) is
# the whole point of this adapter, so mocking nc/js internals the way
# RabbitMQAdapter_test.py mocks pika would mostly just re-describe the
# implementation. Exercising the public port surface against a real NATS
# server is more valuable and far less brittle here.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def nats_url():
    try:
        # Imported here, not at module level: testcontainers is a dev-only
        # dependency of this package (installed via `uv sync --all-extras`
        # from within libs/naas-abi-core, see the Makefile's
        # test-naas-abi-core-integration target) and is absent from the
        # root workspace environment. A top-level import would turn a
        # missing package into a hard collection error for the whole
        # module -- including the fast, non-integration tests below --
        # instead of a clean skip of just this fixture.
        from testcontainers.core.container import DockerContainer

        with (
            DockerContainer("nats:2-alpine")
            .with_command("-js")
            .with_exposed_ports(4222)
        ) as container:
            host = container.get_container_host_ip()
            port = container.get_exposed_port(4222)
            url = f"nats://{host}:{port}"

            deadline = time.time() + 30
            last_exc: Exception | None = None
            probe: NATSJetStreamAdapter | None = None
            while time.time() < deadline:
                try:
                    probe = NATSJetStreamAdapter(nats_url=url)
                    probe.publish("readiness", "probe", b"ping")
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    time.sleep(0.5)
                finally:
                    if probe is not None:
                        probe.close()
            else:
                pytest.fail(f"NATS container did not become ready in time: {last_exc}")

            yield url
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker/Testcontainers unavailable: {exc}")


@pytest.mark.integration
class TestNATSJetStreamAdapterIntegration:
    @pytest.fixture
    def adapter(self, nats_url):
        adapter = NATSJetStreamAdapter(nats_url=nats_url)
        yield adapter
        adapter.close()

    def test_enqueue_dequeue_durable_ack_advances(self, adapter):
        """Work queue: a message is delivered once, and once ACKed a brand
        new dequeue() call (fresh connection, same durable consumer) must
        not redeliver it -- the ack is durable server-side state, not just
        in-memory bookkeeping on the first consumer thread."""
        topic = f"jobs.{uuid.uuid4().hex}"
        routing_key = "created"

        first_received: list[bytes] = []
        first_done = threading.Event()

        def first_callback(payload: bytes) -> None:
            first_received.append(payload)
            first_done.set()
            raise StopIteration()

        adapter.enqueue(topic, routing_key, b"job-1")
        thread_1 = adapter.dequeue(topic, routing_key, first_callback)

        assert first_done.wait(timeout=15)
        thread_1.join(timeout=5)
        assert not thread_1.is_alive()
        assert first_received == [b"job-1"]

        second_received: list[bytes] = []
        second_done = threading.Event()

        def second_callback(payload: bytes) -> None:
            second_received.append(payload)
            second_done.set()
            raise StopIteration()

        adapter.enqueue(topic, routing_key, b"job-2")
        thread_2 = adapter.dequeue(topic, routing_key, second_callback)

        assert second_done.wait(timeout=15)
        thread_2.join(timeout=5)
        assert not thread_2.is_alive()
        # job-1 must NOT reappear here -- proves the ack advanced past it.
        assert second_received == [b"job-2"]

    def test_enqueue_dequeue_competing_consumers_share_durable(self, adapter):
        """Two dequeue() calls on the same (topic, routing_key) compete for
        a shared durable consumer -- every message is delivered exactly
        once across the pair, never to both and never dropped."""
        topic = f"jobs.{uuid.uuid4().hex}"
        routing_key = "created"
        total = 4

        received_a: list[bytes] = []
        received_b: list[bytes] = []
        done = threading.Event()
        lock = threading.Lock()

        def make_callback(bucket: list[bytes]):
            def _callback(payload: bytes) -> None:
                with lock:
                    bucket.append(payload)
                    if len(received_a) + len(received_b) >= total:
                        done.set()
                        raise StopIteration()

            return _callback

        thread_a = adapter.dequeue(topic, routing_key, make_callback(received_a))
        thread_b = adapter.dequeue(topic, routing_key, make_callback(received_b))

        for index in range(total):
            adapter.enqueue(topic, routing_key, f"job-{index}".encode())

        assert done.wait(timeout=15)
        thread_a.join(timeout=2)
        thread_b.join(timeout=2)

        combined = received_a + received_b
        assert len(combined) == total
        assert set(combined) == {f"job-{index}".encode() for index in range(total)}

    def test_publish_subscribe_fanout_to_two_subscribers(self, adapter):
        """Pub/sub: two independent subscribers on the same pattern both
        receive every matching message -- they don't compete."""
        topic = f"evt.{uuid.uuid4().hex}"

        received_a: list[bytes] = []
        received_b: list[bytes] = []
        done_a = threading.Event()
        done_b = threading.Event()

        def make_callback(bucket: list[bytes], done: threading.Event):
            def _callback(payload: bytes) -> None:
                bucket.append(payload)
                if len(bucket) >= 2:
                    done.set()
                    raise StopIteration()

            return _callback

        thread_a = adapter.subscribe(topic, "#", make_callback(received_a, done_a))
        thread_b = adapter.subscribe(topic, "#", make_callback(received_b, done_b))

        # Core NATS pub/sub is live-only -- give both subscriptions a moment
        # to register with the server before publishing, or they'd miss it.
        time.sleep(0.5)

        adapter.publish(topic, "created", b"one")
        adapter.publish(topic, "created", b"two")

        assert done_a.wait(timeout=15)
        assert done_b.wait(timeout=15)
        thread_a.join(timeout=5)
        thread_b.join(timeout=5)

        assert received_a == [b"one", b"two"]
        assert received_b == [b"one", b"two"]


# ---------------------------------------------------------------------------
# A connection lost for good stops the process (naas_abi_sdk.lifeline); one
# the adapter closes itself does not.
# ---------------------------------------------------------------------------


class _FakeConnection:
    """Calls ``closed_cb`` when closed, as nats-py does."""

    def __init__(self, closed_cb, js=None):
        self.closed_cb = closed_cb
        self.is_closed = False
        self.subscribed = asyncio.Event()
        self._js = js

    def jetstream(self):
        return self._js

    async def subscribe(self, subject, cb):
        self.on_message = cb
        self.subscribed.set()
        return MagicMock(unsubscribe=AsyncMock())

    async def close(self) -> None:
        if not self.is_closed:
            self.is_closed = True
            if self.closed_cb is not None:
                await self.closed_cb()

    async def give_up(self) -> None:
        """What nats-py does once it stops reconnecting."""
        self.is_closed = True
        if self.closed_cb is not None:
            await self.closed_cb()


@pytest.fixture
def stops():
    stops: list[str] = []
    restore = lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    yield stops
    restore()


def _fake_connections(monkeypatch, js=None) -> list[_FakeConnection]:
    connections: list[_FakeConnection] = []

    async def connect(url, **options):
        connections.append(_FakeConnection(options.get("closed_cb"), js))
        return connections[-1]

    monkeypatch.setattr(nats, "connect", connect)
    return connections


async def _subscribed(connections, subscriber) -> None:
    """Wait for the subscriber's subscription, or fail with what stopped it."""

    async def wait() -> None:
        while not connections:
            if subscriber.done():
                subscriber.result()
            await asyncio.sleep(0.01)
        await connections[0].subscribed.wait()

    await asyncio.wait_for(wait(), timeout=5)


def _worker(monkeypatch, fetch):
    js = MagicMock(pull_subscribe=AsyncMock(return_value=MagicMock(fetch=fetch)))
    connections = _fake_connections(monkeypatch, js)
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")
    monkeypatch.setattr(adapter, "_ensure_stream_async", AsyncMock(return_value="S"))
    return adapter, connections


def test_the_publish_connection_lost_for_good_stops_the_process(monkeypatch, stops):
    connections = _fake_connections(monkeypatch)
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")
    try:
        adapter._run_coro(adapter._ensure_connection_async())
        adapter._run_coro(connections[0].give_up())
    finally:
        adapter.close()

    assert stops == ["stop"]


def test_closing_the_adapter_is_not_a_loss(monkeypatch, stops):
    connections = _fake_connections(monkeypatch)
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")
    adapter._run_coro(adapter._ensure_connection_async())

    adapter.close()

    assert connections[0].is_closed
    assert stops == []


def test_a_worker_connection_lost_for_good_stops_the_process(monkeypatch, stops):
    async def fetch(batch, timeout):
        await connections[0].give_up()
        raise ConnectionClosedError

    adapter, connections = _worker(monkeypatch, fetch)

    with pytest.raises(ConnectionClosedError):
        asyncio.run(adapter._dequeue_forever("t", "k", lambda body: None))

    assert stops == ["stop"]


def test_a_worker_that_finishes_closes_its_connection_without_a_loss(
    monkeypatch, stops
):
    message = MagicMock(headers=None, data=b"{}", ack=AsyncMock(), nak=AsyncMock())

    async def fetch(batch, timeout):
        return [message]

    def finish(body):
        raise StopIteration

    adapter, connections = _worker(monkeypatch, fetch)

    asyncio.run(adapter._dequeue_forever("t", "k", finish))

    assert connections[0].is_closed
    assert stops == []


def test_a_subscriber_connection_lost_for_good_stops_the_process(monkeypatch, stops):
    connections = _fake_connections(monkeypatch)
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")

    async def scenario():
        subscriber = asyncio.create_task(
            adapter._subscribe_forever("t", "k", lambda body: None)
        )
        await _subscribed(connections, subscriber)
        await connections[0].give_up()
        subscriber.cancel()

    asyncio.run(scenario())

    assert stops == ["stop"]


def test_a_subscriber_that_finishes_closes_its_connection_without_a_loss(
    monkeypatch, stops
):
    connections = _fake_connections(monkeypatch)
    adapter = NATSJetStreamAdapter("nats://127.0.0.1:4222")

    def finish(body):
        raise StopIteration

    async def scenario():
        subscriber = asyncio.create_task(adapter._subscribe_forever("t", "k", finish))
        await _subscribed(connections, subscriber)
        await connections[0].on_message(MagicMock(headers=None, data=b"{}"))
        await subscriber

    asyncio.run(scenario())

    assert connections[0].is_closed
    assert stops == []
