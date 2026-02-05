from dataclasses import dataclass
from queue import Queue
from threading import RLock, Thread
from typing import Callable, Dict, List

from naas_abi_core.services.bus.BusPorts import IBusAdapter


@dataclass(frozen=True)
class _Subscriber:
    routing_key: str
    queue: Queue


class PythonQueueAdapter(IBusAdapter):
    """Process-local bus using stdlib queues (no external deps)."""

    _lock = RLock()
    _subscribers: Dict[str, List[_Subscriber]] = {}

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        with self._lock:
            subscribers = [
                subscriber
                for topic_pattern, topic_subscribers in self._subscribers.items()
                if self._match_routing_key(topic_pattern, topic)
                for subscriber in topic_subscribers
            ]

        for subscriber in subscribers:
            if self._match_routing_key(subscriber.routing_key, routing_key):
                subscriber.queue.put(payload)

    def topic_consume(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        subscriber = _Subscriber(routing_key=routing_key, queue=Queue())
        with self._lock:
            self._subscribers.setdefault(topic, []).append(subscriber)

        def _consume_loop() -> None:
            try:
                while True:
                    payload = subscriber.queue.get()
                    try:
                        callback(payload)
                    except StopIteration:
                        break
                    except Exception:
                        subscriber.queue.put(payload)
                        raise
            finally:
                with self._lock:
                    subscribers = self._subscribers.get(topic, [])
                    if subscriber in subscribers:
                        subscribers.remove(subscriber)
                    if not subscribers and topic in self._subscribers:
                        del self._subscribers[topic]

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _match_routing_key(pattern: str, routing_key: str) -> bool:
        pattern_parts = pattern.split(".") if pattern else [""]
        key_parts = routing_key.split(".") if routing_key else [""]

        def _match(p_index: int, k_index: int) -> bool:
            while True:
                if p_index >= len(pattern_parts):
                    return k_index >= len(key_parts)

                token = pattern_parts[p_index]
                if token == "#":
                    if p_index == len(pattern_parts) - 1:
                        return True
                    for next_index in range(k_index, len(key_parts) + 1):
                        if _match(p_index + 1, next_index):
                            return True
                    return False

                if k_index >= len(key_parts):
                    return False

                if token != "*" and token != key_parts[k_index]:
                    return False

                p_index += 1
                k_index += 1

        return _match(0, 0)
