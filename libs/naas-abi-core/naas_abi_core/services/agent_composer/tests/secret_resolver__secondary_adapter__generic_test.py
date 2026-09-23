"""Contract for ``ISecretResolverPort`` adapters.

Provide a ``resolver`` fixture that knows ``PRESENT=value`` and nothing else.
"""

from abc import ABC

from naas_abi_core.services.agent_composer.AgentComposerPort import ISecretResolverPort


class SecretResolverSecondaryAdapterContract(ABC):
    def test_is_a_resolver_port(self, resolver):
        assert isinstance(resolver, ISecretResolverPort)

    def test_resolves_a_known_secret(self, resolver):
        assert resolver.resolve("PRESENT") == "value"

    def test_unknown_secret_is_none(self, resolver):
        assert resolver.resolve("ABSENT") is None
