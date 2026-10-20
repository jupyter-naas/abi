import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_agents import (
    InMemoryAgentRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import AgentRunStoreContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


class TestInMemoryAgentRunStore(AgentRunStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryAgentRunStore(fixtures.agent_runs(), fixtures.agent_events())


def test_a_failing_store_is_unavailable():
    with pytest.raises(SourceUnavailable):
        asyncio.run(InMemoryAgentRunStore(fail="down").list_runs(["acme.agents"]))
