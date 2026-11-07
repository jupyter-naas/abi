"""In-memory ``IAMSecrets``, for tests and engines without a secret service."""

from __future__ import annotations

import threading

from naas_abi_core.services.iam.IAMPorts import IAMSecrets


class IAMSecretsMemory(IAMSecrets):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        with self._lock:
            return self._values.get(name)

    def put(self, name: str, value: str) -> None:
        with self._lock:
            self._values[name] = value

    def delete(self, name: str) -> None:
        with self._lock:
            self._values.pop(name, None)
