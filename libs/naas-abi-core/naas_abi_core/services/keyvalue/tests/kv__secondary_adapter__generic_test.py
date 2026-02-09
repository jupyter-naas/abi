from abc import ABC, abstractmethod

import pytest


class GenericKVSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        assert callable(getattr(adapter_class, "get", None))
        assert callable(getattr(adapter_class, "set", None))
        assert callable(getattr(adapter_class, "set_if_not_exists", None))
        assert callable(getattr(adapter_class, "delete", None))
        assert callable(getattr(adapter_class, "delete_if_value_matches", None))
        assert callable(getattr(adapter_class, "exists", None))
