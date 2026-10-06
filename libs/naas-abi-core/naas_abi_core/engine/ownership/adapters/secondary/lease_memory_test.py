from contextlib import asynccontextmanager

from naas_abi_core.engine.ownership.adapters.secondary.lease_memory import InMemoryLease
from naas_abi_core.engine.ownership.tests.lease__secondary_adapter__generic_test import (
    GenericLeaseAdapterTest,
)


class TestInMemoryLease(GenericLeaseAdapterTest):
    @asynccontextmanager
    async def open_lease(self):
        yield InMemoryLease()
