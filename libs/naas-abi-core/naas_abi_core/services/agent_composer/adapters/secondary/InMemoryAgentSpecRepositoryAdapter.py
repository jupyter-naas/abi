"""Process-local agent record store, for tests and programmatic registries."""

from __future__ import annotations

import threading
from collections.abc import Iterable

from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentSpec,
    AgentSpecNotFoundError,
    IAgentSpecRepository,
)


class InMemoryAgentSpecRepositoryAdapter(IAgentSpecRepository):
    def __init__(self, specs: Iterable[AgentSpec] = ()) -> None:
        self._lock = threading.Lock()
        self._specs: dict[str, AgentSpec] = {spec.name: spec for spec in specs}

    def get(self, name: str) -> AgentSpec:
        with self._lock:
            spec = self._specs.get(name)
        if spec is None:
            raise AgentSpecNotFoundError(name)
        return spec

    def list(self) -> list[AgentSpec]:
        with self._lock:
            return [self._specs[name] for name in sorted(self._specs)]

    def save(self, spec: AgentSpec) -> None:
        with self._lock:
            self._specs[spec.name] = spec

    def delete(self, name: str) -> None:
        with self._lock:
            if self._specs.pop(name, None) is None:
                raise AgentSpecNotFoundError(name)
