"""Secret resolver backed by the engine's layered ``Secret`` service."""

from __future__ import annotations

from typing import Any, Protocol

from naas_abi_core.services.agent_composer.AgentComposerPort import ISecretResolverPort


class _SecretStore(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...


class SecretServiceResolverAdapter(ISecretResolverPort):
    def __init__(self, secret_service: _SecretStore) -> None:
        self._secrets = secret_service

    def resolve(self, key: str) -> str | None:
        value = self._secrets.get(key, None)
        return None if value in (None, "") else str(value)
