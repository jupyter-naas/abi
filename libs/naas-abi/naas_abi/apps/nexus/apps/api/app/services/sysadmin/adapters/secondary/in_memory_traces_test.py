from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_traces import (
    InMemoryTraceStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    TraceStoreContract,
    UnavailableTraceStoreContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

NOW = datetime(2026, 10, 2, 9, 0, 0, tzinfo=UTC)


class TestInMemoryTraceStore(TraceStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryTraceStore(fixtures.traces(NOW), clock=lambda: NOW)

    @pytest.fixture
    def trace_ids(self):
        return {"a": fixtures.TRACE_A, "b": fixtures.TRACE_B, "c": fixtures.TRACE_C}


class TestUnavailableInMemoryTraceStore(UnavailableTraceStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryTraceStore(fail="jaeger is down")
