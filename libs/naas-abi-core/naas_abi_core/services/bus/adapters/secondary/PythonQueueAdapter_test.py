import threading
from concurrent.futures import ThreadPoolExecutor

from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
    PythonQueueAdapter,
)


def test_publish_across_instances(tmp_path) -> None:
    received: list[bytes] = []
    done = threading.Event()

    db_path = str(tmp_path / "bus-basic.sqlite3")
    consumer = PythonQueueAdapter(persistence_path=db_path)
    publisher = PythonQueueAdapter(persistence_path=db_path)

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.dequeue("events", "user.*", callback)
    publisher.enqueue("events", "user.created", b"ok")

    assert done.wait(timeout=2)
    assert received == [b"ok"]


def test_routing_key_mismatch_is_ignored(tmp_path) -> None:
    received: list[bytes] = []
    done = threading.Event()

    db_path = str(tmp_path / "bus-routing.sqlite3")
    consumer = PythonQueueAdapter(persistence_path=db_path)
    publisher = PythonQueueAdapter(persistence_path=db_path)

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.dequeue("events", "system.#", callback)
    publisher.enqueue("events", "user.created", b"nope")
    publisher.enqueue("events", "system.alerts.high", b"match")

    assert done.wait(timeout=2)
    assert received == [b"match"]


def test_topic_pattern_matches_publish_topic(tmp_path) -> None:
    received: list[bytes] = []
    done = threading.Event()

    db_path = str(tmp_path / "bus-topic.sqlite3")
    consumer = PythonQueueAdapter(persistence_path=db_path)
    publisher = PythonQueueAdapter(persistence_path=db_path)

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.dequeue("events.#", "user.*", callback)
    publisher.enqueue("events.system.alerts", "user.created", b"ok")

    assert done.wait(timeout=2)
    assert received == [b"ok"]


def test_pending_messages_replayed_after_restart(tmp_path) -> None:
    db_path = tmp_path / "bus.sqlite3"
    publisher = PythonQueueAdapter(persistence_path=str(db_path))
    publisher.enqueue("events", "user.created", b"before-consumer")

    done = threading.Event()
    received: list[bytes] = []
    consumer = PythonQueueAdapter(persistence_path=str(db_path))

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.dequeue("events", "user.*", callback)

    assert done.wait(timeout=2)
    assert received == [b"before-consumer"]


def test_concurrent_publish_and_consume(tmp_path) -> None:
    db_path = tmp_path / "bus-concurrency.sqlite3"
    publisher = PythonQueueAdapter(persistence_path=str(db_path))
    consumer = PythonQueueAdapter(persistence_path=str(db_path))

    total = 50
    received: list[bytes] = []
    done = threading.Event()
    lock = threading.Lock()

    def callback(payload: bytes) -> None:
        with lock:
            received.append(payload)
            if len(received) >= total:
                done.set()
                raise StopIteration()

    consumer.dequeue("events", "user.*", callback)

    def publish_one(index: int) -> None:
        publisher.enqueue(
            "events", "user.created", f"msg-{index}".encode("utf-8")
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(publish_one, range(total)))

    assert done.wait(timeout=5)
    assert len(received) == total


# ---------------------------------------------------------------------------
# broadcast (pub/sub) semantics
# ---------------------------------------------------------------------------


def test_broadcast_fans_out_to_every_subscriber(tmp_path) -> None:
    """Two subscribers on the same topic must each receive every message —
    no competition, no dropped events."""
    db_path = str(tmp_path / "bus-broadcast.sqlite3")
    bus = PythonQueueAdapter(persistence_path=db_path, poll_interval_seconds=0.01)

    received_a: list[bytes] = []
    received_b: list[bytes] = []
    sub_a_done = threading.Event()
    sub_b_done = threading.Event()

    def make_cb(received: list[bytes], done: threading.Event):
        def _cb(payload: bytes) -> None:
            received.append(payload)
            if len(received) == 3:
                done.set()
        return _cb

    bus.subscribe("evt.x", "#", make_cb(received_a, sub_a_done))
    bus.subscribe("evt.x", "#", make_cb(received_b, sub_b_done))

    # Give the subscriber loops a moment to capture the initial cursor.
    import time
    time.sleep(0.05)

    bus.publish("evt.x", "evt", b"one")
    bus.publish("evt.x", "evt", b"two")
    bus.publish("evt.x", "evt", b"three")

    assert sub_a_done.wait(timeout=2)
    assert sub_b_done.wait(timeout=2)
    assert received_a == [b"one", b"two", b"three"]
    assert received_b == [b"one", b"two", b"three"]


def test_broadcast_late_subscriber_misses_history(tmp_path) -> None:
    """Redis-style: a subscriber that joins after a publish does NOT see
    the past message. Replay is the event log's job, not the bus."""
    db_path = str(tmp_path / "bus-broadcast-late.sqlite3")
    bus = PythonQueueAdapter(persistence_path=db_path, poll_interval_seconds=0.01)

    bus.publish("evt.y", "evt", b"before-anyone-listens")

    received: list[bytes] = []
    done = threading.Event()

    def cb(payload: bytes) -> None:
        received.append(payload)
        done.set()

    bus.subscribe("evt.y", "#", cb)

    import time
    time.sleep(0.1)
    bus.publish("evt.y", "evt", b"after-subscribe")

    assert done.wait(timeout=2)
    assert received == [b"after-subscribe"]


def test_broadcast_topics_are_isolated(tmp_path) -> None:
    """A subscriber on topic A must not see messages published to topic B."""
    db_path = str(tmp_path / "bus-broadcast-iso.sqlite3")
    bus = PythonQueueAdapter(persistence_path=db_path, poll_interval_seconds=0.01)

    received: list[bytes] = []
    done = threading.Event()

    def cb(payload: bytes) -> None:
        received.append(payload)
        done.set()

    bus.subscribe("topic.a", "#", cb)

    import time
    time.sleep(0.05)

    bus.publish("topic.b", "evt", b"wrong-topic")
    bus.publish("topic.a", "evt", b"right-topic")

    assert done.wait(timeout=2)
    assert received == [b"right-topic"]


def test_broadcast_crosses_adapter_instances(tmp_path) -> None:
    """Two adapter instances pointing at the same DB act like two processes;
    a broadcast from one must reach a subscriber on the other."""
    db_path = str(tmp_path / "bus-broadcast-xproc.sqlite3")
    subscriber_bus = PythonQueueAdapter(
        persistence_path=db_path, poll_interval_seconds=0.01
    )
    publisher_bus = PythonQueueAdapter(
        persistence_path=db_path, poll_interval_seconds=0.01
    )

    received: list[bytes] = []
    done = threading.Event()

    def cb(payload: bytes) -> None:
        received.append(payload)
        done.set()

    subscriber_bus.subscribe("evt.z", "#", cb)

    import time
    time.sleep(0.05)
    publisher_bus.publish("evt.z", "evt", b"hello-other-process")

    assert done.wait(timeout=2)
    assert received == [b"hello-other-process"]


def test_broadcast_failing_subscriber_does_not_block_others(tmp_path) -> None:
    """A subscriber whose callback raises must not stop the other subscriber
    from receiving subsequent messages."""
    db_path = str(tmp_path / "bus-broadcast-fail.sqlite3")
    bus = PythonQueueAdapter(persistence_path=db_path, poll_interval_seconds=0.01)

    received_good: list[bytes] = []
    done = threading.Event()

    def bad_cb(payload: bytes) -> None:
        raise RuntimeError("subscriber boom")

    def good_cb(payload: bytes) -> None:
        received_good.append(payload)
        if len(received_good) == 2:
            done.set()

    bus.subscribe("evt.w", "#", bad_cb)
    bus.subscribe("evt.w", "#", good_cb)

    import time
    time.sleep(0.05)

    bus.publish("evt.w", "evt", b"first")
    bus.publish("evt.w", "evt", b"second")

    assert done.wait(timeout=2)
    assert received_good == [b"first", b"second"]
