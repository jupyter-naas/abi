from threading import Thread
from typing import Callable

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

    def __init__(self, adapter: IBusAdapter):
        super().__init__()
        self.__adapter = adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
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
        self.__publish_event(
            BusMessagePublished(
                topic=topic,
                routing_key=routing_key,
                size_bytes=len(payload),
            )
        )
        return result

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
