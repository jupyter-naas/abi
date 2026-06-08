from abc import ABC, abstractmethod

import pytest


class GenericBusSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        # Pub/sub: every matching subscriber receives every matching message.
        assert callable(getattr(adapter_class, "publish", None))
        assert callable(getattr(adapter_class, "subscribe", None))
        # Work queue: exactly one consumer per message, durable.
        assert callable(getattr(adapter_class, "enqueue", None))
        assert callable(getattr(adapter_class, "dequeue", None))
