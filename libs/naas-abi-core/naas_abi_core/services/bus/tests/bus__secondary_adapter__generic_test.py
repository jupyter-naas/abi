from abc import ABC, abstractmethod

import pytest


class GenericBusSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        assert callable(getattr(adapter_class, "topic_publish", None))
        assert callable(getattr(adapter_class, "topic_consume", None))
