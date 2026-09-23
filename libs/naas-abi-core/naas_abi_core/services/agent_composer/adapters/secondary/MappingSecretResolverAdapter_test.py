import pytest
from naas_abi_core.services.agent_composer.adapters.secondary.MappingSecretResolverAdapter import (
    MappingSecretResolverAdapter,
)
from naas_abi_core.services.agent_composer.tests.secret_resolver__secondary_adapter__generic_test import (
    SecretResolverSecondaryAdapterContract,
)


class TestMappingSecretResolverAdapter(SecretResolverSecondaryAdapterContract):
    @pytest.fixture
    def resolver(self):
        return MappingSecretResolverAdapter({"PRESENT": "value"})
