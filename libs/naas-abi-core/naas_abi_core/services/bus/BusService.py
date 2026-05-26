from threading import Thread
from typing import Callable

from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.ServiceBase import ServiceBase


class BusService(ServiceBase):
    __adapter: IBusAdapter

    def __init__(self, adapter: IBusAdapter):
        super().__init__()
        self.__adapter = adapter

    # Pub/sub — ephemeral, fanout, routing-key matched.
    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        return self.__adapter.publish(topic, routing_key, payload)

    def subscribe(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        return self.__adapter.subscribe(topic, routing_key, callback)

    # Work queue — durable, exactly-one consumer per message.
    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        return self.__adapter.enqueue(topic, routing_key, payload)

    def dequeue(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        return self.__adapter.dequeue(topic, routing_key, callback)
