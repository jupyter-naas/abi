"""IAM test fixtures: a bootstrapped service on the memory store."""

import pytest

from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import (
    ACTIVITY_LOG,
    NEXUS,
    TRIPLE_STORE,
    IAMHarness,
)


@pytest.fixture
def iam() -> IAMService:
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    service._register_catalog(TRIPLE_STORE)
    service._register_catalog(ACTIVITY_LOG)
    service._register_catalog(NEXUS)
    return service


@pytest.fixture
def h(iam) -> IAMHarness:
    return IAMHarness(iam)
