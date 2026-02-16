import threading
import time

from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
    PythonQueueAdapter,
)


def _clear_subscribers() -> None:
    with PythonQueueAdapter._lock:
        PythonQueueAdapter._subscribers.clear()


def _wait_for_subscriber(topic: str) -> None:
    for _ in range(50):
        with PythonQueueAdapter._lock:
            if PythonQueueAdapter._subscribers.get(topic):
                return
        time.sleep(0.01)
    raise AssertionError("subscriber not registered")


def _wait_for_unsubscribe(topic: str) -> None:
    for _ in range(50):
        with PythonQueueAdapter._lock:
            if not PythonQueueAdapter._subscribers.get(topic):
                return
        time.sleep(0.01)
    raise AssertionError("subscriber not removed")


def test_publish_across_instances() -> None:
    _clear_subscribers()
    received = []
    done = threading.Event()

    consumer = PythonQueueAdapter()
    publisher = PythonQueueAdapter()

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.topic_consume("events", "user.*", callback)
    _wait_for_subscriber("events")

    publisher.topic_publish("events", "user.created", b"ok")

    assert done.wait(timeout=1)
    _wait_for_unsubscribe("events")
    assert received == [b"ok"]


def test_routing_key_mismatch_is_ignored() -> None:
    _clear_subscribers()
    received = []
    done = threading.Event()

    consumer = PythonQueueAdapter()
    publisher = PythonQueueAdapter()

    def callback(payload: bytes) -> None:
        received.append(payload)
        if payload == b"match":
            done.set()
            raise StopIteration()

    consumer.topic_consume("events", "system.#", callback)
    _wait_for_subscriber("events")

    publisher.topic_publish("events", "user.created", b"nope")
    publisher.topic_publish("events", "system.alerts.high", b"match")

    assert done.wait(timeout=1)
    _wait_for_unsubscribe("events")
    assert received == [b"match"]


def test_topic_pattern_matches_publish_topic() -> None:
    _clear_subscribers()
    received = []
    done = threading.Event()

    consumer = PythonQueueAdapter()
    publisher = PythonQueueAdapter()

    def callback(payload: bytes) -> None:
        received.append(payload)
        done.set()
        raise StopIteration()

    consumer.topic_consume("events.#", "user.*", callback)
    _wait_for_subscriber("events.#")

    publisher.topic_publish("events.system.alerts", "user.created", b"ok")

    assert done.wait(timeout=1)
    _wait_for_unsubscribe("events.#")
    assert received == [b"ok"]
