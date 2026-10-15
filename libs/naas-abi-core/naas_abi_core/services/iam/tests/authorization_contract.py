"""The authorization contract every kernel service passes (RFC §5.4).

A service's test subclasses ``AuthorizationContract`` once per operation it
wants to pin, and provides:

* ``ACTION``: the qualified action the operation needs;
* ``NOT_FOUND``: what a caller who cannot see the resource gets (the service's
  own not-found error, else ``ResourceNotFoundError``);
* ``owner(contract_iam, tmp_path)``: a fixture building the owning domain
  service, wired with ``contract_iam`` (``wire(service, iam)``);
* ``primary(owner)``: the NATS primary adapter serving ``owner`` (``start(nc)``
  and ``stop()``), and ``facade(nats_url, identity)``: the domain service a
  remote caller holds, over that adapter's NATS client;
* ``resource(owner)``: the canonical name the operation is checked on;
* ``call(service)``: the operation, on the owner or on the facade;
* optionally ``prepare(owner)``: setup run as the engine before each test.

Each outcome runs for two callers, ``api`` acting for an IAM user and a
recorded service account, in process and over a live NATS server; both
transports must give the same outcome:

* no policy: the service's not-found error (the caller cannot see it);
* granted: the operation succeeds;
* explicit deny of the action, with every other action of the service
  allowed: permission denied, or not found when no other action applies to the
  resource's type (the caller then cannot see it).

NATS cases need ``nats-server`` on ``PATH`` and skip otherwise.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event as ThreadingEvent
from threading import Thread
from typing import Any, ClassVar

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    use_call_context,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.nats_test_server import (
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    PrincipalRecord,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.kernel_catalogs import kernel_catalogs
from naas_abi_core.services.iam.names import parse_resource_name
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

JWT_SECRET = "authorization-contract-secret"
TRANSPORTS = ("in_process", "nats")
CALLERS = ("user_via_api", "service_account")
SERVICE_ACCOUNT = "contract-module"


def contract_iam() -> IAMService:
    """A bootstrapped IAM on the memory store, with every kernel catalog."""
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    for catalog in kernel_catalogs():
        iam._register_catalog(catalog)
    return iam


def wire(service: Any, iam: IAMService, **others: Any) -> Any:
    """Wire a domain service with IAM, as the engine wires an owner."""
    service.set_services(IEngine.Services(iam=iam, **others))
    return service


class PrimaryServer:
    """Runs a NATS primary adapter on its own event loop, for a test."""

    def __init__(self, nats_url: str, primary: Any) -> None:
        self.nats_url, self.primary = nats_url, primary
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: Any = None

    def start(self) -> None:
        import nats

        ready = ThreadingEvent()
        errors: list[BaseException] = []

        async def start() -> None:
            self._nc = await nats.connect(self.nats_url)
            await self.primary.start(self._nc)

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(start())
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                ready.set()
            if not errors:
                loop.run_forever()
            loop.close()

        self._thread = Thread(target=run, daemon=True, name="contract-primary")
        self._thread.start()
        ready.wait(timeout=15)
        if errors:
            raise errors[0]

    def stop(self) -> None:
        loop = self._loop
        if loop is None:
            return

        async def stop() -> None:
            await self.primary.stop()
            await self._nc.close()

        try:
            asyncio.run_coroutine_threadsafe(stop(), loop).result(timeout=5)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5)


@contextmanager
def nats_server() -> Iterator[str]:
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with (
        tempfile.TemporaryDirectory() as workdir,
        native_nats_server(Path(workdir)) as url,
    ):
        yield url


class AuthorizationContract:
    ACTION: ClassVar[str]
    NOT_FOUND: ClassVar[tuple[type[BaseException], ...]] = (ResourceNotFoundError,)

    # -- what a service provides ------------------------------------------------

    @pytest.fixture
    def owner(self, contract_iam: IAMService, tmp_path: Path) -> Any:
        raise NotImplementedError

    def primary(self, owner: Any) -> Any:
        raise NotImplementedError

    def facade(self, nats_url: str, identity: str) -> Any:
        raise NotImplementedError

    def resource(self, owner: Any) -> str:
        raise NotImplementedError

    def call(self, service: Any) -> Any:
        raise NotImplementedError

    def prepare(self, owner: Any) -> None:
        """Setup run as the engine before each test (a resource to read...)."""

    def close_facade(self, facade: Any) -> None:
        for name in ("close", "adapter"):
            target = getattr(facade, name, None)
            if name == "adapter" and target is not None:
                target = getattr(target, "close", None)
            if callable(target):
                target()
                return

    # -- the harness ---------------------------------------------------------------

    @pytest.fixture
    def contract_iam(self) -> IAMService:
        return contract_iam()

    @pytest.fixture
    def h(self, contract_iam: IAMService) -> IAMHarness:
        return IAMHarness(contract_iam)

    @pytest.fixture(scope="class")
    def nats_url(self) -> Iterator[str]:
        with nats_server() as url:
            yield url

    @pytest.fixture(params=TRANSPORTS)
    def transport(self, request: pytest.FixtureRequest) -> str:
        return request.param

    @pytest.fixture(params=CALLERS)
    def caller(self, request: pytest.FixtureRequest, h: IAMHarness) -> PrincipalRecord:
        if request.param == "user_via_api":
            return h.user("contract-user")
        return h.service_account(SERVICE_ACCOUNT)

    @pytest.fixture
    def invoke(
        self,
        request: pytest.FixtureRequest,
        owner: Any,
        transport: str,
        caller: PrincipalRecord,
    ) -> Iterator[Callable[[], Any]]:
        from naas_abi_core.engine.call_context import as_service_account

        with as_service_account("engine"):
            self.prepare(owner)
        context = _context(caller)
        if transport == "in_process":

            def local() -> Any:
                with use_call_context(context):
                    return self.call(owner)

            yield local
            return
        nats_url = request.getfixturevalue("nats_url")
        server = PrimaryServer(nats_url, self.primary(owner))
        server.start()
        identity = "api" if caller.kind == "user" else (caller.name or caller.id)
        facade = self.facade(nats_url, identity)
        try:

            def remote() -> Any:
                with use_call_context(context):
                    return self.call(facade)

            yield remote
        finally:
            self.close_facade(facade)
            server.stop()

    def _grant(self, h: IAMHarness, caller: PrincipalRecord, *statements: dict) -> None:
        h.grant(caller.id, *statements)

    # -- the contract ---------------------------------------------------------------

    def test_a_caller_with_no_policy_cannot_see_the_resource(self, invoke) -> None:
        with pytest.raises(self.NOT_FOUND):
            invoke()

    def test_a_granted_caller_succeeds(self, invoke, h, caller, owner) -> None:
        self._grant(
            h, caller, statement("Allow", [self.ACTION], [self.resource(owner)])
        )
        invoke()

    def test_an_explicit_deny_wins(
        self, invoke, h, caller, owner, contract_iam
    ) -> None:
        """Deny beats Allow. The caller still sees the resource, and gets
        permission denied, when another action on its type stays allowed;
        otherwise not found (§5.4)."""
        service = self.ACTION.split(":", 1)[0]
        name = self.resource(owner)
        self._grant(
            h,
            caller,
            statement("Allow", [f"{service}:*"], [name]),
            statement("Deny", [self.ACTION], [name]),
        )
        others = set(
            contract_iam.catalogs.actions_on(service, parse_resource_name(name).type)
        ) - {self.ACTION}
        with pytest.raises(PermissionDeniedError if others else self.NOT_FOUND):
            invoke()


def _context(caller: PrincipalRecord) -> CallContext:
    if caller.kind == "user":
        return CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            on_behalf_of=Principal(id=caller.id, kind="user"),
        )
    name = caller.name or caller.id
    return CallContext(principal=Principal(id=name, kind="service_account", name=name))
