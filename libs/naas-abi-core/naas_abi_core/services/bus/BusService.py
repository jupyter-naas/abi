from threading import Thread
from typing import Callable

from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.ServiceBase import ServiceBase


class BusService(ServiceBase):
    __adapter: IBusAdapter

    def __init__(self, adapter: IBusAdapter):
        super().__init__()
        self.__adapter = adapter

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        return self.__adapter.topic_publish(topic, routing_key, payload)

    def topic_consume(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        return self.__adapter.topic_consume(topic, routing_key, callback)
