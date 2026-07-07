from abc import ABC, abstractmethod

import pytest

REQUIRED_METHODS = (
    "ensure_user",
    "list_templates",
    "provision",
    "list_environments",
    "get_logs",
    "start",
    "stop",
    "delete",
    "get_status",
    "get_access",
)


class GenericCodingEnvironmentSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        for method in REQUIRED_METHODS:
            assert callable(getattr(adapter_class, method, None)), (
                f"adapter is missing required method: {method}"
            )
