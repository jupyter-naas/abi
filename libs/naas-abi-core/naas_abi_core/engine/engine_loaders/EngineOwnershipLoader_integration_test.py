"""Engine handover on a real broker: callers see no failed call.

A crash still loses the requests the engine had already received: nobody knows
whether they ran, so they are not sent again. Requests sent after it are answered.

Each "engine" is an ownership loader plus a queue-grouped responder standing in
for the kernel services; the caller sends through ``no_responders`` as the
engine's and the SDK's clients do.
"""

import asyncio
import threading
import time
from typing import Self

import nats
import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
    EngineOwnershipLoader,
)
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    EngineAlreadyServing,
)
from naas_abi_sdk import no_responders

SUBJECT = "abi.svc.handover.v1.echo"
pytestmark = pytest.mark.integration


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True) as url:
        yield url


class FakeEngine:
    """A loader and the services it serves once it holds the lease."""

    def __init__(self, url: str, name: str, rollout_id: str = ""):
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

    def serve(self) -> None:
        async def start():
            self.nc = await nats.connect(self.url)

            async def answer(msg):
                await msg.respond(self.name.encode())

            self.sub = await self.nc.subscribe(SUBJECT, queue="owners", cb=answer)
            await self.nc.flush()

        self.loader.run(start())

    def stop_serving(self) -> None:
        if self.sub is not None:
            sub, self.sub = self.sub, None
            self.loader.run(sub.drain())

    def callbacks(self):
        return {"on_fenced": self.stop_serving, "on_restored": self.serve}

    def shutdown(self) -> None:
        """Engine.shutdown's order: release the lease, then drain the services."""
        self.loader.release()
        self.stop_serving()
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
    old = FakeEngine(broker, "old", "v1")
    assert old.loader.claim() is Claim.SERVING
    old.serve()
    old.loader.keep(**old.callbacks())
    new = FakeEngine(broker, "new", "v2")
    assert new.loader.claim() is Claim.STANDBY
    new.loader.take_over_in_background(new.serve, **new.callbacks())

    with Caller(broker) as caller:
        caller.wait_for("old")
        old.shutdown()
        caller.wait_for("new")

    assert caller.failures == []
    assert caller.answers.index("new") > caller.answers.index("old")
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
