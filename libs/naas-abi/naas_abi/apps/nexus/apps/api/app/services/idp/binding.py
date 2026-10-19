"""Which provider is the built-in IdP, and which module answers for it.

The route at ``/idp`` serves one module, and only one: the instance of module
``idp`` that runs as the service account ``module/<project>/idp``, and only
while the engine's ``identity.providers`` has a provider with
``provisioning: builtin``. The module is configured, never discovered: a module
that registered itself as ``idp`` under another account is not served.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    engine_services,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from naas_abi_core.services.iam.modules import account_name, subject_token
from starlette.concurrency import run_in_threadpool

IDP_MODULE = "idp"
IDP_APP = "idp"
# What the route asks of the engine, as Nexus's own account.
NEXUS_IDENTITY = "api"
CACHE_SECONDS = 10.0


class IdpNotConfigured(Exception):
    """No provider is the built-in IdP: the route answers 404."""


class IdpUnavailable(Exception):
    """The built-in IdP is configured but cannot be reached: 503."""


@dataclass(frozen=True)
class IdpTarget:
    service_account: str  # the subject token of the account the module runs as
    issuer: str


def _providers() -> list[Any]:
    services = engine_services()
    if services is None or not services.identity_available():
        raise IdpNotConfigured("The engine has no identity service")
    with as_service_account(NEXUS_IDENTITY):
        return list(services.identity.list_providers())


def _project() -> str:
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
        _engine_nats_configuration,
    )

    nats = _engine_nats_configuration()
    discovery = getattr(nats, "discovery", None)
    if discovery is None:
        raise IdpUnavailable("The built-in IdP runs over NATS: nats.discovery is not configured")
    return str(discovery.project)


def _account(project: str) -> str:
    services = engine_services()
    if services is None:
        raise IdpUnavailable("No engine")
    with as_service_account(NEXUS_IDENTITY):
        try:
            record = services.iam.find_service_account(account_name(project, IDP_MODULE))
        except IAMNotFoundError as exc:
            raise IdpUnavailable(
                f"The service account module/{project}/{IDP_MODULE} does not exist"
            ) from exc
    return subject_token(record.id)


class IdpBinding:
    def __init__(
        self,
        providers: Callable[[], list[Any]] = _providers,
        project: Callable[[], str] = _project,
        account: Callable[[str], str] = _account,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._providers, self._project, self._account = providers, project, account
        self._clock = clock
        self._cached: tuple[float, IdpTarget] | None = None

    async def target(self) -> IdpTarget:
        now = self._clock()
        if self._cached is not None and now - self._cached[0] < CACHE_SECONDS:
            return self._cached[1]
        target = await run_in_threadpool(self._resolve)
        self._cached = (now, target)
        return target

    def _resolve(self) -> IdpTarget:
        builtin = next((p for p in self._providers() if p.provisioning == "builtin"), None)
        if builtin is None:
            raise IdpNotConfigured("No identity provider is the built-in IdP")
        project = self._project()
        return IdpTarget(self._account(project), builtin.issuer)


BINDING = IdpBinding()


def configure(binding: IdpBinding) -> IdpBinding:
    """Replace the binding (tests); returns the previous one."""
    global BINDING
    previous, BINDING = BINDING, binding
    return previous
