import pytest
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    IAMStoreContract,
)


class TestIAMStoreMemory(IAMStoreContract):
    @pytest.fixture
    def store(self):
        store = IAMStoreMemory()
        yield store
        store.close()
