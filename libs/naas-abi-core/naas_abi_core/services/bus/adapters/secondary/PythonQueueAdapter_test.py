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

    consumer.topic_consume("events", "user.*", callback)
    publisher.topic_publish("events", "user.created", b"ok")

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

    consumer.topic_consume("events", "system.#", callback)
    publisher.topic_publish("events", "user.created", b"nope")
    publisher.topic_publish("events", "system.alerts.high", b"match")

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

    consumer.topic_consume("events.#", "user.*", callback)
    publisher.topic_publish("events.system.alerts", "user.created", b"ok")

    assert done.wait(timeout=2)
    assert received == [b"ok"]


def test_pending_messages_replayed_after_restart(tmp_path) -> None:
    db_path = tmp_path / "bus.sqlite3"
    publisher = PythonQueueAdapter(persistence_path=str(db_path))
    publisher.topic_publish("events", "user.created", b"before-consumer")

    done = threading.Event()
    received: list[bytes] = []
    consumer = PythonQueueAdapter(persistence_path=str(db_path))

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.topic_consume("events", "user.*", callback)

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

    consumer.topic_consume("events", "user.*", callback)

    def publish_one(index: int) -> None:
        publisher.topic_publish(
            "events", "user.created", f"msg-{index}".encode("utf-8")
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(publish_one, range(total)))

    assert done.wait(timeout=5)
    assert len(received) == total
