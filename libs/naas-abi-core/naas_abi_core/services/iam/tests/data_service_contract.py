"""The authorization contract of the data services (RFC §5, §6.4).

A data service subclasses ``DataServiceContract`` beside its domain service
(``<Service>_authorization_test.py``) and provides
the hooks: its domain service over a real local adapter, its NATS primary, a
domain-shaped client over its NATS secondary adapter, the resources a policy
grants and denies, and the cases to run. The contract then runs the cases, in
order, for each of three service accounts, in process and over NATS, each
from freshly seeded data, and checks that

* a principal with no policy gets nothing: reads and writes are refused, lists
  are empty;
* a granted principal reaches what its Allow covers, and lists show only that;
* a principal allowed everything but explicitly denied some resources is
  refused those (Deny beats Allow) and lists hide them; denied only writes on
  others, it reads them and gets ``PERMISSION_DENIED`` writing them;
* in process and over NATS give the same results, since the check lives in the
  domain service.

Outcomes are compared, not exceptions: ``OK`` (with the case's view of the
value), ``NOT_FOUND`` (the resource is invisible, §5.4) or ``DENIED`` (visible,
not allowed). ``outcome_of`` maps a service's own errors to them.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    service_account,
    use_call_context,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.enforcement import internal_call
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import document, statement

# The verifier the primaries serve with; a client's token names its identity
# (``TEST_TOKENS.source``).
SECRET = TEST_TOKENS.verifier
NOBODY, GRANTED, DENIED = "nobody", "granted", "denied"
PRINCIPALS = (NOBODY, GRANTED, DENIED)
OK, NOT_FOUND, REFUSED = "ok", "not_found", "denied"


@dataclass(frozen=True)
class Expect:
    """An outcome, and for ``OK`` optionally the value the case's view gives."""

    outcome: str
    value: Any = field(default=None)
    check_value: bool = False


def ok(value: Any) -> Expect:
    return Expect(OK, value, check_value=True)


ANY_OK = Expect(OK)
HIDDEN = Expect(NOT_FOUND)
DENY = Expect(REFUSED)


@dataclass(frozen=True)
class Case:
    """One call, and what each principal gets from it."""

    name: str
    call: Callable[[Any], Any]
    nobody: Expect
    granted: Expect
    denied: Expect
    view: Callable[[Any], Any] = lambda value: value

    def expected(self, principal: str) -> Expect:
        return {NOBODY: self.nobody, GRANTED: self.granted, DENIED: self.denied}[
            principal
        ]


class EventLoopThread:
    """An event loop on its own thread, for a primary adapter under test."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coroutine: Any, timeout: float = 30.0) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
        self.loop.close()


def caller(name: str) -> CallContext:
    return CallContext(principal=service_account(name))


class DataServiceContract:
    """Subclass it in a service's tests and fill in the hooks."""

    catalog: ActionCatalog

    # -- hooks ----------------------------------------------------------------

    def build_owner(self, tmp_path: Path) -> Any:
        """The domain service over a real local adapter (not yet wired)."""
        raise NotImplementedError

    def seed(self, owner: Any) -> None:
        """Write the data the cases read; runs as the engine."""

    def build_primary(self, owner: Any) -> Any:
        """The service's NATS primary adapter around ``owner``."""
        raise NotImplementedError

    def build_remote(self, url: str, identity: str) -> Any:
        """A domain-shaped client of the primary, over NATS, as ``identity``."""
        raise NotImplementedError

    def close_remote(self, remote: Any) -> None:
        """Close what ``build_remote`` opened."""

    def granted_resources(self) -> list[str]:
        """The resource patterns the granted principal may act on."""
        raise NotImplementedError

    def denied_resources(self) -> list[str]:
        """The resource patterns denied to the otherwise allowed principal."""
        raise NotImplementedError

    def read_only_resources(self) -> list[str]:
        """Patterns on which the otherwise allowed principal is denied every
        write and admin action: it sees them, so a write is ``DENIED``."""
        return []

    def cases(self) -> list[Case]:
        raise NotImplementedError

    def outcome_of(self, exc: BaseException) -> str | None:
        """The outcome a service error stands for, beyond IAM's own."""
        return None

    def other_services(self, iam: IAMService) -> dict[str, Any]:
        """Other services the owner is wired with (by ``IEngine.Services`` name)."""
        return {}

    # -- the contract -------------------------------------------------------------

    def iam(self) -> IAMService:
        iam = IAMService(IAMStoreMemory())
        iam.bootstrap()
        with internal_call():
            iam.register_catalog(self.catalog)
            for name in (NOBODY, GRANTED, DENIED):
                iam.create_service_account(name)
            granted = iam.create_policy(
                "granted",
                document(
                    statement(
                        "Allow",
                        [f"{self.catalog.service}:*"],
                        self.granted_resources(),
                    )
                ),
            )
            iam.attach_policy(granted.id, self._id(iam, GRANTED))
            denied = iam.create_policy(
                "denied",
                document(
                    statement("Allow", [f"{self.catalog.service}:*"], ["*"]),
                    statement(
                        "Deny", [f"{self.catalog.service}:*"], self.denied_resources()
                    ),
                    *(
                        [
                            statement(
                                "Deny",
                                [
                                    self.catalog.qualified(a.name)
                                    for a in self.catalog.actions
                                    if a.level in ("write", "admin")
                                ],
                                self.read_only_resources(),
                            )
                        ]
                        if self.read_only_resources()
                        else []
                    ),
                ),
            )
            iam.attach_policy(denied.id, self._id(iam, DENIED))
        return iam

    @staticmethod
    def _id(iam: IAMService, name: str) -> str:
        record = iam.store.find_service_account(name)
        assert record is not None
        return record.id

    def _owner(self, tmp_path: Path) -> tuple[Any, IAMService]:
        iam = self.iam()
        owner = self.build_owner(tmp_path)
        owner.set_services(IEngine.Services(iam=iam, **self.other_services(iam)))
        with internal_call():
            self.seed(owner)
        return owner, iam

    def _outcome(self, case: Case, call: Callable[[], Any]) -> tuple[str, Any]:
        try:
            value = call()
        except PermissionDeniedError:
            return (REFUSED, None)
        except ResourceNotFoundError:
            return (NOT_FOUND, None)
        except Exception as exc:
            mapped = self.outcome_of(exc)
            if mapped is None:
                raise
            return (mapped, None)
        return (OK, case.view(value))

    def run_in_process(self, tmp_path: Path) -> dict[tuple[str, str], tuple[str, Any]]:
        results = {}
        for principal in PRINCIPALS:
            # Each principal starts from the same seeded state.
            owner, _ = self._owner(tmp_path / "in-process" / principal)
            for case in self.cases():
                with use_call_context(caller(principal)):
                    results[(case.name, principal)] = self._outcome(
                        case, partial(case.call, owner)
                    )
        return results

    @contextmanager
    def _served(self, owner: Any, url: str) -> Iterator[None]:
        import nats

        loop = EventLoopThread()
        nc = loop.run(nats.connect(url))
        primary = self.build_primary(owner)
        loop.run(primary.start(nc))
        loop.run(nc.flush())
        try:
            yield
        finally:
            loop.run(primary.stop())
            loop.run(nc.close())
            loop.close()

    def run_over_nats(
        self, tmp_path: Path, url: str
    ) -> dict[tuple[str, str], tuple[str, Any]]:
        results = {}
        for principal in PRINCIPALS:
            owner, _ = self._owner(tmp_path / "nats" / principal)
            with self._served(owner, url):
                remote = self.build_remote(url, principal)
                try:
                    for case in self.cases():
                        results[(case.name, principal)] = self._outcome(
                            case, partial(case.call, remote)
                        )
                finally:
                    self.close_remote(remote)
        return results

    def check(self, results: dict[tuple[str, str], tuple[str, Any]], where: str):
        failures = []
        for case in self.cases():
            for principal in PRINCIPALS:
                expected = case.expected(principal)
                outcome, value = results[(case.name, principal)]
                if outcome != expected.outcome or (
                    expected.check_value and value != expected.value
                ):
                    failures.append(
                        f"{where} {case.name} as {principal}: got {outcome} {value!r}, "
                        f"expected {expected.outcome}"
                        + (f" {expected.value!r}" if expected.check_value else "")
                    )
        assert not failures, "\n".join(failures)

    # -- tests ----------------------------------------------------------------------

    def test_in_process(self, tmp_path):
        self.check(self.run_in_process(tmp_path), "in process")

    @pytest.mark.integration
    def test_over_nats_as_in_process(self, tmp_path):
        from naas_abi_core.engine.nats_test_server import (
            native_nats_server,
            nats_server_binary,
        )

        if nats_server_binary() is None:
            pytest.skip("nats-server is not installed")
        in_process = self.run_in_process(tmp_path)
        with native_nats_server(tmp_path) as url:
            over_nats = self.run_over_nats(tmp_path, url)
        self.check(over_nats, "over NATS")
        checked = {
            (case.name, principal): case.expected(principal).check_value
            for case in self.cases()
            for principal in PRINCIPALS
        }

        def seen(outcome: tuple[str, Any], key: tuple[str, str]) -> Any:
            # Values a case does not check (ids, timestamps) may differ.
            return outcome if checked[key] else outcome[0]

        differences = [
            f"{case} as {principal}: in process {in_process[(case, principal)]!r}, "
            f"over NATS {over_nats[(case, principal)]!r}"
            for case, principal in in_process
            if seen(in_process[(case, principal)], (case, principal))
            != seen(over_nats[(case, principal)], (case, principal))
        ]
        assert not differences, "\n".join(differences)
