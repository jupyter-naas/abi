"""``IAMSecrets`` in the secret service: IAM's signing keys and the engine's
own service key, under ``iam/`` (sealed to ``engine``, RFC §11.3).

Give it the secret service built from this engine's local adapters (dotenv,
naas, ...), never a ``nats_rpc`` one: an engine reads its signing keys before
it can call anything over NATS.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from naas_abi_core import logger
from naas_abi_core.services.iam.IAMPorts import IAMSecrets
from naas_abi_core.services.secret.SecretPorts import ISecretService

PREFIX = "iam/"


class IAMSecretsSecretService(IAMSecrets):
    """``secrets``: the secret service, or a factory building it on first use
    (an engine that never issues a token never opens it). When it cannot be
    built, IAM keeps its secrets in memory and says so: tokens then die with
    the process."""

    def __init__(self, secrets: ISecretService | Callable[[], ISecretService]) -> None:
        self._source = secrets
        self._secrets: ISecretService | None = None
        self._memory: dict[str, str] | None = None
        self._lock = threading.Lock()

    def _service(self) -> ISecretService | None:
        with self._lock:
            if self._secrets is None and self._memory is None:
                if callable(self._source) and not isinstance(
                    self._source, ISecretService
                ):
                    try:
                        self._secrets = self._source()
                    except Exception as exc:  # noqa: BLE001 - fall back, loudly
                        logger.warning(
                            f"IAM keeps its signing keys in memory: no secret service ({exc})"
                        )
                        self._memory = {}
                else:
                    self._secrets = self._source  # type: ignore[assignment]
            return self._secrets

    def get(self, name: str) -> str | None:
        service = self._service()
        if service is None:
            return (self._memory or {}).get(_checked(name))
        value = service.get(_checked(name))
        return value if isinstance(value, str) and value else None

    def put(self, name: str, value: str) -> None:
        service = self._service()
        if service is None:
            assert self._memory is not None
            self._memory[_checked(name)] = value
            return
        service.set(_checked(name), value)

    def delete(self, name: str) -> None:
        service = self._service()
        if service is None:
            (self._memory or {}).pop(_checked(name), None)
            return
        service.remove(_checked(name))


def _checked(name: str) -> str:
    if not name.startswith(PREFIX):
        raise ValueError(f"IAM keeps its secrets under {PREFIX}: {name!r}")
    return name
