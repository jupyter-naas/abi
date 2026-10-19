"""The built-in IdP's ``idp`` app, called over NATS as the engine.

Like Nexus's remote-app directory, but for one module only, and only the one
bound to the IdP: the instance of module ``idp`` (``IDP_MODULE``) that runs as
the service account ``module/<project>/idp``. Discovery's instance carries that
account's subject token, so an instance of the same module id under another
account is never called: the engine sends the client secret of its sign-in
there, so who answers matters.

``request`` is synchronous (the identity service is) and runs on the engine's
shared NATS loop (``engine.nats_runtime``).
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable, Mapping
from typing import Any

from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
    AppAnswer,
    IdPApp,
)
from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError

IDP_MODULE = "idp"
IDP_APP = "idp"
CONTRACT_MAJOR = 1
# Discovery is read at most this often.
SNAPSHOT_SECONDS = 10.0
# A little over the module's own idle limit for a request it answers.
TIMEOUT_SECONDS = 20.0


class IdPAppNATS(IdPApp):
    def __init__(
        self,
        *,
        nats_url: str,
        project: str,
        token: Callable[[], str],
        host_token: Callable[[str], str],
        service_account: Callable[[], str | None],
        timeout: float = TIMEOUT_SECONDS,
        run: Callable[..., Any] | None = None,
    ) -> None:
        """``service_account``: the subject token of the account the IdP runs
        as (None while it is not created). ``run``: how a coroutine runs to
        completion from this thread (the engine's NATS runtime by default)."""
        self._url, self._project = nats_url, project
        self._token, self._host_token = token, host_token
        self._service_account = service_account
        self._timeout = timeout
        self._run = run
        self._client: tuple[Any, Any] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._snapshot: tuple[float, list[tuple[str, str]]] | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        query: str = "",
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
        root_path: str = "",
    ) -> AppAnswer:
        coroutine = self._request(method, path, query, body, headers or {}, root_path)
        if self._run is not None:
            return self._run(coroutine, timeout=self._timeout + 5)  # type: ignore[no-any-return]
        from naas_abi_core.engine import nats_runtime

        return nats_runtime.run_coro(coroutine, timeout=self._timeout + 5)  # type: ignore[no-any-return]

    async def _request(
        self,
        method: str,
        path: str,
        query: str,
        body: bytes,
        headers: Mapping[str, str],
        root_path: str,
    ) -> AppAnswer:
        from naas_abi_proto.app.v1 import app_pb2 as pb
        from naas_abi_sdk.app_host import call_app
        from naas_abi_sdk.transport import RPCError
        from nats.errors import NoRespondersError

        transport, discovery = self._clients()
        instances = await self._instances(discovery)
        if not instances:
            raise ProviderUnavailableError(
                "No instance of the built-in identity provider is ready "
                f"(module {IDP_MODULE!r} of project {self._project!r})"
            )
        message = pb.HttpRequest(
            app=IDP_APP,
            method=method,
            path=path,
            query=query,
            body=body,
            root_path=root_path,
        )
        for name, value in headers.items():
            message.headers.add(name=name, value=value)
        random.shuffle(instances)
        last = "no instance answered"
        for service_account, instance_id in instances[:2]:  # one retry, elsewhere
            try:
                response = await call_app(
                    transport,
                    self._project,
                    instance_id,
                    message,
                    service_account=service_account,
                )
            except (RPCError, NoRespondersError, TimeoutError) as exc:
                last = str(exc) or type(exc).__name__
                self._snapshot = None  # that instance is gone or going
                continue
            if response.body_follows:
                raise ProviderUnavailableError(
                    "The built-in identity provider streamed an answer"
                )
            return AppAnswer(
                response.status or 200,
                tuple((h.name, h.value) for h in response.headers),
                bytes(response.body),
            )
        raise ProviderUnavailableError(f"The built-in identity provider: {last}")

    def _clients(self) -> tuple[Any, Any]:
        loop = asyncio.get_running_loop()
        if self._client is None or self._loop is not loop:
            from naas_abi_sdk.discovery import DiscoveryClient
            from naas_abi_sdk.transport import Transport

            transport = Transport(
                self._url,
                self._token,
                timeout=self._timeout,
                host_token=self._host_token,  # type: ignore[arg-type]
            )
            self._client = (transport, DiscoveryClient(transport, self._project))
            self._loop = loop
            self._snapshot = None
        return self._client

    async def _instances(self, discovery: Any) -> list[tuple[str, str]]:
        """``(service account, instance id)`` of each ready instance of the IdP
        that runs as the IdP's account."""
        now = time.monotonic()
        if self._snapshot is not None and now - self._snapshot[0] < SNAPSHOT_SECONDS:
            return list(self._snapshot[1])
        account = self._service_account()
        found: list[tuple[str, str]] = []
        if account is not None:
            after = ""
            while True:
                page, after = await discovery.list_modules(
                    limit=100, after_instance_id=after
                )
                for instance in page:
                    if (
                        instance.module_id == IDP_MODULE
                        and instance.service_account == account
                        and instance.status == "READY"
                        and instance.contract_major == CONTRACT_MAJOR
                        and any(
                            a.name == IDP_APP for a in getattr(instance, "apps", ())
                        )
                    ):
                        found.append((instance.service_account, instance.instance_id))
                if not after:
                    break
        if found:  # an IdP that is not up yet is looked for again at once
            self._snapshot = (now, found)
        return list(found)
