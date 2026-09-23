"""Secret resolver over a plain mapping (tests, scripts, injected config)."""

from __future__ import annotations

from collections.abc import Mapping

from naas_abi_core.services.agent_composer.AgentComposerPort import ISecretResolverPort


class MappingSecretResolverAdapter(ISecretResolverPort):
    def __init__(self, secrets: Mapping[str, str]) -> None:
        self._secrets = dict(secrets)

    def resolve(self, key: str) -> str | None:
        return self._secrets.get(key)
