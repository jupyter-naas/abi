import pytest
from naas_abi_core.services.agent_composer.adapters.secondary.InMemoryAgentSpecRepositoryAdapter import (
    InMemoryAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.AgentComposerPort import AgentSpec
from naas_abi_core.services.agent_composer.tests.agent_spec_repository__secondary_adapter__generic_test import (
    AgentSpecRepositorySecondaryAdapterContract,
)


class TestInMemoryAgentSpecRepositoryAdapter(
    AgentSpecRepositorySecondaryAdapterContract
):
    @pytest.fixture
    def repository(self):
        return InMemoryAgentSpecRepositoryAdapter()

    def test_can_be_seeded(self):
        spec = AgentSpec(name="seeded", prompt="Hi.")
        assert InMemoryAgentSpecRepositoryAdapter([spec]).get("seeded") == spec
