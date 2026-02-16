from abc import ABC, abstractmethod
from threading import Thread
from typing import Callable


class IBusAdapter(ABC):
    @abstractmethod
    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        raise NotImplementedError()

    @abstractmethod
    def topic_consume(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        raise NotImplementedError()
