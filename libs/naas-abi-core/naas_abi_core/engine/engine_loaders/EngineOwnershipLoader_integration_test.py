"""Engine handover on a real broker: callers see no failed call.

A crash still loses the requests the engine had already received: nobody knows
whether they ran, so they are not sent again. Requests sent after it are answered.

Each "engine" is an ownership loader plus a queue-grouped responder standing in
for the kernel services; the caller sends through ``no_responders`` as the
engine's and the SDK's clients do. In a deploy, the engines also serve the real
key-value primary over one shared store, called through the engine's NATS client.
"""

import asyncio
import threading
import time
from typing import Self
from unittest.mock import Mock

import nats
import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
    EngineOwnershipLoader,
)
from naas_abi_core.engine.nats_sessions import (
    SessionHost,
    stop_delivery,
    wait_for_sessions,
)
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    EngineAlreadyServing,
)
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
    PythonAdapter,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter
from naas_abi_sdk import no_responders

SUBJECT = "abi.svc.handover.v1.echo"
SECRET = "engine-ownership-test-secret-at-least-32-bytes"
pytestmark = pytest.mark.integration


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True) as url:
        yield url


class SharedStore(PythonAdapter):
    """The key-value backend every engine of a deploy shares, slow enough that
    calls are in flight, and waiting behind each other, at the handover."""

    def get(self, key):
        time.sleep(0.03)
        return super().get(key)

    def set(self, key, value, ttl=None):
        time.sleep(0.03)
        super().set(key, value, ttl)


class FakeEngine:
    """A loader and the services it serves once it holds the lease."""

    def __init__(
        self,
        url: str,
        name: str,
        rollout_id: str = "",
        store: IKeyValueAdapter | None = None,
    ):
        self.url, self.name = url, name
        self.lost = threading.Event()
        self.loader = EngineOwnershipLoader(
            NATSConfiguration(
                nats_url=url, jwt_secret="test-only", engine={"lease_seconds": 1}
            ),
            environ={"ABI_ROLLOUT_ID": rollout_id} if rollout_id else {},
            on_lost=self.lost.set,
        )
        self.nc = None
        self.sub = None
        # This engine's view of the shared store: counts the calls it served.
        self.store = None if store is None else Mock(spec=IKeyValueAdapter, wraps=store)
        self.primaries: list = []

    def serve(self) -> None:
        async def start():
            self.nc = await nats.connect(self.url)

            async def answer(msg):
                await msg.respond(self.name.encode())

            self.sub = await self.nc.subscribe(SUBJECT, queue="owners", cb=answer)
            if self.store is not None:
                primary = KeyValuePrimaryAdapterNATS(self.store, SECRET)
                await primary.start(self.nc)
                self.primaries = [primary]
            await self.nc.flush()

        self.loader.run(start())

    def stop_serving(self) -> None:
        """Fencing: the responder answers what it received, the primaries stop."""
        if self.sub is not None:
            sub, self.sub = self.sub, None
            self.loader.run(stop_delivery([sub]))
            self.loader.run(sub.drain())
        primaries, self.primaries = self.primaries, []
        for primary in primaries:
            self.loader.run(primary.stop())

    def callbacks(self):
        return {"on_fenced": self.stop_serving, "on_restored": self.serve}

    def served(self) -> int:
        """Key-value calls this engine answered."""
        return 0 if self.store is None else len(self.store.method_calls)

    def shutdown(self, drain_seconds: float = 10) -> None:
        """Engine.shutdown's order: release the lease, end the shared
        subscriptions, answer the calls already received, then close."""
        self.loader.release()
        primaries, self.primaries = self.primaries, []
        hosts = [p for p in primaries if isinstance(p, SessionHost)]
        for primary in primaries:
            self.loader.run(
                primary.stop_accepting() if primary in hosts else primary.stop()
            )
        self.stop_serving()
        self.loader.run(wait_for_sessions(hosts, drain_seconds), drain_seconds + 5)
        for host in hosts:
            self.loader.run(host.stop())
        if self.nc is not None:
            self.loader.run(self.nc.close())
        self.loader.close()


class Caller:
    """Sends a request every 10 ms on its own thread and records every outcome."""

    def __init__(self, url: str):
        self.url = url
        self.answers: list[str] = []
        self.failures: list[tuple[float, str]] = []  # (sent at, error)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=lambda: asyncio.run(self._run()))

    async def _run(self) -> None:
        nc = await nats.connect(self.url)
        while not self._stop.is_set():
            sent = time.monotonic()
            try:
                reply = await no_responders.request(
                    nc, SUBJECT, b"ping", headers={}, timeout=5
                )
                self.answers.append(reply.data.decode())
            except Exception as exc:  # noqa: BLE001 - recorded for the assertion
                self.failures.append((sent, repr(exc)))
            await asyncio.sleep(0.01)
        await nc.close()

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def wait_for(self, name: str, timeout: float = 10) -> None:
        deadline = time.monotonic() + timeout
        while name not in self.answers[-5:]:
            assert time.monotonic() < deadline, f"{name} never answered"
            time.sleep(0.02)


class KeyValueCallers:
    """Threads that each write a key then read it back, without pause, through
    the engine's key-value NATS client, and record every failure."""

    def __init__(self, url: str, count: int = 3):
        self.url = url
        self.failures: list[str] = []
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._run, args=(f"key-{n}",)) for n in range(count)
        ]

    def _run(self, key: str) -> None:
        client = KeyValueSecondaryAdapterNATSClient(
            self.url, SECRET, "caller", timeout_seconds=5
        )
        n = 0
        while not self._stop.is_set():
            n += 1
            value = f"{key}={n}".encode()
            try:
                client.set(key, value)
                read = client.get(key)
                if read != value:
                    self.failures.append(f"{key}: wrote {value!r}, read {read!r}")
            except Exception as exc:  # noqa: BLE001 - recorded for the assertion
                self.failures.append(f"{key}: {exc!r}")
        client.close()

    def __enter__(self) -> Self:
        for thread in self._threads:
            thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=15)

    def wait_for(self, engine: FakeEngine, calls: int = 20, timeout: float = 15):
        """Until ``engine`` has answered ``calls`` more calls."""
        target = engine.served() + calls
        deadline = time.monotonic() + timeout
        while engine.served() < target:
            assert time.monotonic() < deadline, f"{engine.name} answered no call"
            time.sleep(0.02)


def test_a_second_engine_without_a_new_rollout_fails_to_start(broker):
    first = FakeEngine(broker, "first")
    assert first.loader.claim() is Claim.SERVING
    first.loader.keep(**first.callbacks())
    second = FakeEngine(broker, "second")

    started = time.monotonic()
    with pytest.raises(EngineAlreadyServing):
        second.loader.claim()

    assert time.monotonic() - started < 1.5
    second.loader.close()
    first.shutdown()


def test_a_deploy_hands_over_without_a_failed_call(broker):
    store = SharedStore()
    old = FakeEngine(broker, "old", "v1", store)
    assert old.loader.claim() is Claim.SERVING
    old.serve()
    old.loader.keep(**old.callbacks())
    new = FakeEngine(broker, "new", "v2", store)
    assert new.loader.claim() is Claim.STANDBY
    new.loader.take_over_in_background(new.serve, **new.callbacks())

    with Caller(broker) as caller, KeyValueCallers(broker) as kernel:
        caller.wait_for("old")
        kernel.wait_for(old)
        old.shutdown()
        caller.wait_for("new")
        kernel.wait_for(new)

    assert caller.failures == []
    assert caller.answers.index("new") > caller.answers.index("old")
    # One-shot kernel calls in flight at the handover were answered too.
    assert kernel.failures == []
    assert not new.lost.is_set()
    new.shutdown()


def test_a_standby_answers_every_request_sent_after_a_crash(broker):
    old = FakeEngine(broker, "old", "v1")
    assert old.loader.claim() is Claim.SERVING
    old.serve()
    old.loader.keep(**old.callbacks())
    new = FakeEngine(broker, "new", "v2")
    assert new.loader.claim() is Claim.STANDBY
    new.loader.take_over_in_background(new.serve, **new.callbacks())

    with Caller(broker) as caller:
        caller.wait_for("old")
        # The process dies: renewals stop and its connections drop, no release.
        old.loader._keeping.cancel()
        old.loader.run(old.nc.close())
        # Past this, the broker has dropped the old engine's subscription.
        crashed_at = time.monotonic() + 0.1
        caller.wait_for("new")

    assert [f for f in caller.failures if f[0] >= crashed_at] == []
    new.shutdown()
    old.loader.close()
