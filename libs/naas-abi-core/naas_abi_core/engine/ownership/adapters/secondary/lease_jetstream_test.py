from contextlib import asynccontextmanager
from uuid import uuid4

import nats
import pytest
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.ownership.adapters.secondary.lease_jetstream import (
    JetStreamLease,
)
from naas_abi_core.engine.ownership.tests.lease__secondary_adapter__generic_test import (
    GenericLeaseAdapterTest,
    holder,
)


@pytest.fixture(scope="module")
def broker(tmp_path_factory):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path_factory.mktemp("lease"), jetstream=True) as url:
        yield url


class TestJetStreamLease(GenericLeaseAdapterTest):
    @pytest.fixture(autouse=True)
    def _broker(self, broker):
        self.url = broker

    @asynccontextmanager
    async def open_lease(self):
        nc = await nats.connect(self.url)
        try:
            # A bucket per test: each starts on an empty store.
            yield await JetStreamLease.open(nc, bucket=f"ABI_ENGINE_{uuid4().hex}")
        finally:
            await nc.close()

    def test_two_connections_share_one_lease(self):
        async def scenario(_):
            bucket = f"ABI_ENGINE_{uuid4().hex}"
            first, second = await nats.connect(self.url), await nats.connect(self.url)
            try:
                a = await JetStreamLease.open(first, bucket=bucket)
                b = await JetStreamLease.open(second, bucket=bucket)
                await a.create(holder("a"))

                assert (await b.read()).holder == holder("a")
            finally:
                await first.close()
                await second.close()

        self.run(scenario)

    def test_a_foreign_value_reads_as_an_unknown_holder(self):
        async def scenario(lease):
            await lease.bucket.put(lease.key, b"not json")

            record = await lease.read()

            assert record.holder.instance_id == ""
            assert record.revision > 0

        self.run(scenario)
