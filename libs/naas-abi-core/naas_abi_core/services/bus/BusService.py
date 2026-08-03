from collections.abc import Callable, Sequence
from threading import Thread

from naas_abi_core import logger
from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.bus.ontologies.modules.BusEventOntology import (
    BusError,
    BusMessageEnqueued,
    BusMessagePublished,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class BusService(ServiceBase):
    __adapter: IBusAdapter

    def __init__(self, adapter: IBusAdapter, emit_message_events: bool = False):
        """Wrap ``adapter`` with optional event-log telemetry.

        ``emit_message_events`` turns on a durable ``BusMessagePublished`` /
        ``BusMessageEnqueued`` event for *every* message crossing the bus.
        It defaults to **off**: the bus is a high-volume transport, and one
        fsync'd event-log append per message is a 3x write amplification that
        drowns real events. Engine boot alone publishes one message per
        ontology triple, so leaving this on costs tens of thousands of event
        rows before the process serves its first request.

        Turn it on deliberately when debugging bus traffic. ``BusError``
        events are always emitted — failures are rare and worth recording.
        """
        super().__init__()
        self.__adapter = adapter
        self._emit_message_events = emit_message_events

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:  # noqa: BLE001
            # Bus is the source of truth; event logging must never break it.
            logger.warning(f"BusService: failed to publish event: {exc}")

    # Pub/sub — ephemeral, fanout, routing-key matched.
    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        # Recursion guard: EventService.publish() calls bus.publish() to
        # broadcast events on "evt.*" topics. Emitting a BusMessagePublished
        # for those would re-enter EventService.publish() → infinite loop.
        if topic.startswith("evt."):
            return self.__adapter.publish(topic, routing_key, payload)
        try:
            result = self.__adapter.publish(topic, routing_key, payload)
        except Exception as exc:
            self.__publish_event(
                BusError(
                    topic=topic,
                    routing_key=routing_key,
                    operation="publish",
                    message=str(exc),
                )
            )
            raise
        if self._emit_message_events:
            self.__publish_event(
                BusMessagePublished(
                    topic=topic,
                    routing_key=routing_key,
                    size_bytes=len(payload),
                )
            )
        return result

    def publish_many(
        self, topic: str, messages: Sequence[tuple[str, bytes]]
    ) -> None:
        """Publish a batch of ``(routing_key, payload)`` pairs on ``topic``.

        Delivery is identical to calling :meth:`publish` per message; the
        adapter is free to commit the batch in one round-trip. Prefer this
        over a publish loop whenever the message count scales with input
        size (bulk triple inserts, imports, backfills).
        """
        if not messages:
            return
        if topic.startswith("evt."):
            return self.__adapter.publish_many(topic, messages)
        try:
            self.__adapter.publish_many(topic, messages)
        except Exception as exc:
            self.__publish_event(
                BusError(
                    topic=topic,
                    routing_key=messages[0][0],
                    operation="publish_many",
                    message=str(exc),
                )
            )
            raise
        if self._emit_message_events:
            for routing_key, payload in messages:
                self.__publish_event(
                    BusMessagePublished(
                        topic=topic,
                        routing_key=routing_key,
                        size_bytes=len(payload),
                    )
                )

    def subscribe(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        return self.__adapter.subscribe(topic, routing_key, callback)

    # Work queue — durable, exactly-one consumer per message.
    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        if topic.startswith("evt."):
            return self.__adapter.enqueue(topic, routing_key, payload)
        try:
            result = self.__adapter.enqueue(topic, routing_key, payload)
        except Exception as exc:
            self.__publish_event(
                BusError(
                    topic=topic,
                    routing_key=routing_key,
                    operation="enqueue",
                    message=str(exc),
                )
            )
            raise
        if self._emit_message_events:
            self.__publish_event(
                BusMessageEnqueued(
                    topic=topic,
                    routing_key=routing_key,
                    size_bytes=len(payload),
                )
            )
        return result

    def dequeue(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        return self.__adapter.dequeue(topic, routing_key, callback)
