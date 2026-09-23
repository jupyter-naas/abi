import pytest
from naas_abi_core.services.agent_composer.adapters.secondary.SecretServiceResolverAdapter import (
    SecretServiceResolverAdapter,
)
from naas_abi_core.services.agent_composer.tests.secret_resolver__secondary_adapter__generic_test import (
    SecretResolverSecondaryAdapterContract,
)


class _FakeSecretService:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestSecretServiceResolverAdapter(SecretResolverSecondaryAdapterContract):
    @pytest.fixture
    def resolver(self):
        return SecretServiceResolverAdapter(_FakeSecretService({"PRESENT": "value"}))

    def test_empty_values_count_as_unset(self):
        resolver = SecretServiceResolverAdapter(_FakeSecretService({"EMPTY": ""}))
        assert resolver.resolve("EMPTY") is None

    def test_works_with_the_engine_secret_service(self):
        from naas_abi_core.services.secret.Secret import Secret

        class _Adapter:
            def get(self, key, default=None):
                return {"PRESENT": "value"}.get(key, default)

            def set(self, key, value): ...
            def remove(self, key): ...
            def list(self):
                return {"PRESENT": "value"}

        service = Secret([_Adapter()])
        assert SecretServiceResolverAdapter(service).resolve("PRESENT") == "value"
