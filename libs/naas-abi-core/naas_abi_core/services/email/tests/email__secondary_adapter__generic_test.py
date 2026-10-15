from abc import ABC, abstractmethod

import pytest


class GenericEmailSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        assert callable(getattr(adapter_class, "send", None))
        for method in ("list_sent", "get_sent", "delete_sent"):
            assert callable(getattr(adapter_class, method, None))
